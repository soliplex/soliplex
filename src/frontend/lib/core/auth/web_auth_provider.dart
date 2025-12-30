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
sealed class PendingServerResult {
  const PendingServerResult();
}

/// A pending server ID was found.
final class PendingServerFound extends PendingServerResult {
  /// Creates a found result.
  const PendingServerFound(this.serverId);

  /// The server ID.
  final String serverId;
}

/// No pending server ID exists.
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
/// On web, [login] throws [AuthFlowRedirect] since the browser navigates
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
        _pendingStorage = pendingStorage,
        _httpClient = httpClient,
        _callbackPath = callbackPath,
        _urlLauncher = urlLauncher;

  final String _baseUrl;
  final TokenStorage _tokenStorage;
  final WebAuthPendingStorage _pendingStorage;
  final http.Client _httpClient;
  final String _callbackPath;
  final UrlLauncher _urlLauncher;

  @override
  Future<AuthResult> getValidToken(String serverId, SsoConfig config) async {
    final result = await _tokenStorage.read(serverId);

    switch (result) {
      case TokenNotFound():
        return const NoToken();
      case TokenFound(:final token):
        if (!token.needsRefresh) {
          return Authenticated(token: token);
        }

        if (!token.canRefresh) {
          await _tokenStorage.delete(serverId);
          return const TokenExpired();
        }

        final refreshResult = await _attemptRefresh(token, config);
        switch (refreshResult) {
          case RefreshSuccess(:final token):
            await _tokenStorage.write(serverId, token);
            return Authenticated(token: token);
          case RefreshRejected(:final cause):
            await _tokenStorage.delete(serverId);
            return RefreshFailed(cause: cause);
        }
    }
  }

  @override
  Future<AuthToken> login(String serverId, SsoConfig config) async {
    // Store server ID for retrieval after callback
    await _pendingStorage.savePendingServerId(serverId);

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

    // Signal that browser redirect is happening
    // Callers should catch this and wait for callback
    throw AuthFlowRedirect(serverId: serverId);
  }

  @override
  Future<void> logout(String serverId) async {
    // Clear local tokens - no server-side logout for web flow
    await _tokenStorage.delete(serverId);
    await _pendingStorage.clearPendingServerId();
    debugPrint('WebAuthProvider: Logged out $serverId');
  }

  @override
  Future<UserInfo> getCurrentUser(String serverId, SsoConfig config) async {
    final result = await _tokenStorage.read(serverId);

    final token = switch (result) {
      TokenFound(:final token) => token,
      TokenNotFound() => throw const AuthErrorNotAuthenticated(),
    };

    final userInfoEndpoint = config.userInfoEndpoint;
    if (userInfoEndpoint == null) {
      throw const AuthErrorConfiguration(
        message: 'No userinfo endpoint configured',
      );
    }

    final http.Response response;
    try {
      response = await _httpClient.get(
        Uri.parse(userInfoEndpoint),
        headers: {'Authorization': 'Bearer ${token.accessToken}'},
      );
    } on Exception catch (e, st) {
      throw AuthErrorNetwork(
        message: 'Failed to fetch user info: $e',
        originalError: e,
        stackTrace: st,
      );
    }

    if (response.statusCode != 200) {
      throw AuthErrorServer(
        message: 'User info request failed',
        statusCode: response.statusCode,
        body: response.body,
      );
    }

    final json = jsonDecode(response.body) as Map<String, dynamic>;
    return UserInfo.fromOidcClaims(json);
  }

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
          expiresAt: DateTime.now().add(Duration(seconds: expiresIn)),
          idToken: json['id_token'] as String?,
        ),
      );
    } on Exception catch (e) {
      return RefreshRejected(e.toString());
    }
  }
}
