import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:soliplex_client/soliplex_client.dart';
import 'package:url_launcher/url_launcher.dart' as url_launcher;

/// Function type for launching URLs.
typedef UrlLauncher = Future<bool> Function(
  Uri url, {
  url_launcher.LaunchMode mode,
  String? webOnlyWindowName,
});

/// Default URL launcher using url_launcher package.
Future<bool> defaultUrlLauncher(
  Uri url, {
  url_launcher.LaunchMode mode = url_launcher.LaunchMode.platformDefault,
  String? webOnlyWindowName,
}) {
  return url_launcher.launchUrl(
    url,
    mode: mode,
    webOnlyWindowName: webOnlyWindowName,
  );
}

/// Storage for pending web authentication state.
///
/// Persists the server ID between browser redirect and callback.
abstract interface class WebAuthPendingStorage {
  /// Save the server ID before redirecting to OIDC provider.
  Future<void> savePendingServerId(String serverId);

  /// Retrieve the server ID after callback.
  Future<PendingServerResult> getPendingServerId();

  /// Clear pending server ID after successful auth or error.
  Future<void> clearPendingServerId();
}

/// Result of retrieving a pending server ID.
@immutable
sealed class PendingServerResult {
  const PendingServerResult();
}

/// A pending server ID was found.
@immutable
final class PendingServerFound extends PendingServerResult {
  /// Creates a found result.
  const PendingServerFound(this.serverId);

  /// The server ID.
  final String serverId;
}

/// No pending server ID exists.
@immutable
final class NoPendingServer extends PendingServerResult {
  /// Creates a not found result.
  const NoPendingServer();
}

/// AuthProvider implementation for web and desktop (Windows/Linux).
///
/// Uses backend-mediated OAuth flow:
/// 1. Redirect to backend `/api/login/{system}?return_to=...`
/// 2. Backend performs OAuth exchange with OIDC provider
/// 3. Backend redirects back with tokens in URL query params
///
/// On web, [login] returns [LoginRedirect] since the browser navigates
/// away. The callback URL is handled by a separate screen that extracts
/// tokens and stores them.
///
/// Token refresh is performed via direct HTTP POST to the OIDC token endpoint.
class WebAuthProvider implements AuthProvider {
  /// Creates a web auth provider.
  ///
  /// The [baseUrl] is the Soliplex backend URL (e.g., 'https://api.example.com').
  /// The [callbackPath] is the app route that handles OAuth callbacks
  /// (default: '/auth/callback').
  /// The [urlLauncher] is injectable for testing (defaults to
  /// [defaultUrlLauncher]).
  WebAuthProvider({
    required String baseUrl,
    required TokenStorage tokenStorage,
    required WebAuthPendingStorage pendingStorage,
    required http.Client httpClient,
    String callbackPath = '/auth/callback',
    UrlLauncher urlLauncher = defaultUrlLauncher,
  })  : _baseUrl = baseUrl,
        _tokenStorage = tokenStorage,
        _tokenValidator = TokenValidator(tokenStorage: tokenStorage),
        _pendingStorage = pendingStorage,
        _httpClient = httpClient,
        _callbackPath = callbackPath,
        _urlLauncher = urlLauncher,
        _userInfoFetcher = UserInfoFetcher(
          tokenStorage: tokenStorage,
          httpClient: httpClient,
        );

  final String _baseUrl;
  final TokenStorage _tokenStorage;
  final TokenValidator _tokenValidator;
  final WebAuthPendingStorage _pendingStorage;
  final http.Client _httpClient;
  final String _callbackPath;
  final UrlLauncher _urlLauncher;
  final UserInfoFetcher _userInfoFetcher;

  @override
  Future<AuthResult> getValidToken(String serverId, SsoConfig config) =>
      _tokenValidator.getValidToken(
        serverId,
        onRefresh: (token) => _attemptRefresh(token, config),
      );

  @override
  Future<LoginResult> login(String serverId, SsoConfig config) async {
    // Build the backend login URL
    final loginUrl = Uri.parse('$_baseUrl/api/login/${config.authSystem.id}')
        .replace(queryParameters: {'return_to': _callbackPath});

    debugPrint('WebAuthProvider: Redirecting to $loginUrl');

    // Launch browser - on web this navigates away from the app
    final launched = await _urlLauncher(
      loginUrl,
      mode: url_launcher.LaunchMode.inAppBrowserView,
      webOnlyWindowName: '_self',
    );

    if (!launched) {
      throw const AuthErrorNetwork(
        message: 'Failed to open authentication URL',
      );
    }

    // Store server ID only after successful URL launch
    await _pendingStorage.savePendingServerId(serverId);

    // Browser is redirecting; caller should wait for callback
    return LoginRedirect(serverId: serverId);
  }

  /// Logs out by clearing local tokens only.
  ///
  /// **Limitation**: This does NOT perform server-side logout with the OIDC
  /// provider. The user's session with the identity provider remains active.
  /// If the user logs in again, they may be automatically authenticated
  /// without re-entering credentials (SSO behavior).
  ///
  /// This limitation exists because the web flow uses backend-mediated
  /// authentication, and implementing server-side logout would require either:
  /// - A backend endpoint that performs the OIDC end-session redirect, or
  /// - Exposing the end-session URL to the client (security tradeoff)
  ///
  /// For use cases requiring full logout, consider implementing a backend
  /// `/api/logout` endpoint that handles the OIDC end-session flow.
  @override
  Future<void> logout(String serverId, SsoConfig config) async {
    await _tokenStorage.delete(serverId);
    await _pendingStorage.clearPendingServerId();
    debugPrint('WebAuthProvider: Logged out $serverId');
  }

  @override
  Future<UserInfo> getCurrentUser(String serverId, SsoConfig config) =>
      _userInfoFetcher.fetch(serverId, config);

  /// Attempts to refresh the token using the OIDC token endpoint.
  Future<RefreshResult> _attemptRefresh(
    AuthToken token,
    SsoConfig config,
  ) async {
    try {
      final response = await _httpClient.post(
        Uri.parse(config.tokenEndpoint),
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: {
          'grant_type': 'refresh_token',
          'refresh_token': token.refreshToken,
          'client_id': config.clientId,
        },
      );

      if (response.statusCode != 200) {
        return RefreshRejected(
          'Token refresh failed: ${response.statusCode} ${response.body}',
        );
      }

      final json = jsonDecode(response.body) as Map<String, dynamic>;
      final accessToken = json['access_token'] as String?;
      final expiresIn = json['expires_in'] as int?;
      final refreshToken = json['refresh_token'] as String?;

      if (accessToken == null || expiresIn == null) {
        return const RefreshRejected('Invalid token response from server');
      }

      return RefreshSuccess(
        AuthToken(
          accessToken: accessToken,
          refreshToken: refreshToken ?? token.refreshToken,
          expiresAt: DateTime.now().toUtc().add(Duration(seconds: expiresIn)),
          idToken: json['id_token'] as String?,
        ),
      );
    } on http.ClientException catch (e) {
      return RefreshRejected('Network error during refresh: $e');
    } on FormatException catch (e) {
      return RefreshRejected('Invalid token response format: $e');
    }
  }
}
