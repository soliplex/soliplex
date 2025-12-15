import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:soliplex/core/auth/oidc_auth_token_response.dart';
import 'package:soliplex/core/auth/secure_token_storage.dart';
import 'package:soliplex/core/auth/web_auth_callback_stub.dart'
    if (dart.library.js_interop) 'web_auth_callback_web.dart'
    as platform;
import 'package:soliplex/core/auth/web_auth_pending_storage.dart';
import 'package:soliplex/core/network/network_inspector.dart';
import 'package:soliplex/core/utils/debug_log.dart';
import 'package:soliplex/core/utils/http_config.dart';

/// Result of processing an auth callback
sealed class AuthCallbackResult {}

/// Successful authentication
class AuthCallbackSuccess extends AuthCallbackResult {
  AuthCallbackSuccess({required this.serverId, required this.tokens});

  /// The server ID we authenticated to
  final String serverId;

  /// The tokens received
  final OidcAuthTokenResponse tokens;
}

/// Authentication failed
class AuthCallbackFailure extends AuthCallbackResult {
  AuthCallbackFailure({required this.error, this.description});

  /// Error message
  final String error;

  /// Optional error description from OIDC provider
  final String? description;

  @override
  String toString() => description != null ? '$error: $description' : error;
}

/// No callback detected (not on callback URL)
class AuthCallbackNotDetected extends AuthCallbackResult {}

/// Handles the OIDC authorization callback.
///
/// When the browser redirects back from the OIDC provider, this handler:
/// 1. Extracts the authorization code and state from the URL
/// 2. Validates the state (CSRF protection)
/// 3. Exchanges the code for tokens
/// 4. Stores the tokens
/// 5. Returns the server ID for navigation
class WebAuthCallbackHandler {
  WebAuthCallbackHandler({
    required WebAuthPendingStorage pendingStorage,
    required SecureTokenStorage tokenStorage,
    NetworkInspector? inspector,
  }) : _pendingStorage = pendingStorage,
       _tokenStorage = tokenStorage,
       _inspector = inspector;
  final WebAuthPendingStorage _pendingStorage;
  final SecureTokenStorage _tokenStorage;
  final NetworkInspector? _inspector;

  /// Check if we're on an auth callback URL
  bool isAuthCallback() => platform.isAuthCallback();

  /// Get current URL path (for logging/debugging)
  String getCurrentPath() => platform.getCurrentPath();

  /// Process the auth callback
  ///
  /// Returns AuthCallbackSuccess with server ID and tokens on success,
  /// AuthCallbackFailure on error, or AuthCallbackNotDetected if not on
  /// callback URL.
  Future<AuthCallbackResult> handleCallback() async {
    DebugLog.auth('WebAuthCallbackHandler: Checking for callback...');
    DebugLog.auth('WebAuthCallbackHandler: Current path: ${getCurrentPath()}');

    // Check if we're on the callback URL
    if (!isAuthCallback()) {
      DebugLog.auth('WebAuthCallbackHandler: Not on callback URL');
      return AuthCallbackNotDetected();
    }

    // Extract parameters from URL
    final (code, state, error) = platform.extractCallbackParams();
    DebugLog.auth(
      // ignore: lines_longer_than_80_chars (auto-documented)
      'WebAuthCallbackHandler: Extracted params - code: ${code != null}, state: ${state != null}, error: $error',
    );

    // Check for error response from OIDC provider
    if (error != null) {
      DebugLog.error('WebAuthCallbackHandler: OIDC error: $error');
      await _pendingStorage.clearPendingAuth();
      platform.clearUrlParams();
      return AuthCallbackFailure(error: error);
    }

    // Validate we have code and state
    if (code == null || state == null) {
      DebugLog.error('WebAuthCallbackHandler: Missing code or state');
      await _pendingStorage.clearPendingAuth();
      platform.clearUrlParams();
      return AuthCallbackFailure(error: 'Missing authorization code or state');
    }

    // Get pending auth data
    final pending = await _pendingStorage.getPendingAuth();
    if (pending == null) {
      DebugLog.error('WebAuthCallbackHandler: No pending auth found');
      platform.clearUrlParams();
      return AuthCallbackFailure(
        error: 'No pending authentication',
        description:
            'The authentication session may have expired. Please try again.',
      );
    }

    // Validate state (CSRF protection)
    if (pending.state != state) {
      DebugLog.error('WebAuthCallbackHandler: State mismatch!');
      await _pendingStorage.clearPendingAuth();
      platform.clearUrlParams();
      return AuthCallbackFailure(
        error: 'State mismatch',
        description: 'Security validation failed. Please try again.',
      );
    }

    DebugLog.auth(
      'WebAuthCallbackHandler: State validated, exchanging code for tokens...',
    );

    // Exchange code for tokens
    try {
      final tokens = await _exchangeCodeForTokens(
        code: code,
        codeVerifier: pending.codeVerifier,
        clientId: pending.clientId,
        redirectUrl: pending.redirectUrl,
        tokenEndpoint: pending.tokenEndpoint,
      );

      // Store tokens
      await _tokenStorage.setOidcAuthTokenResponse(tokens);
      DebugLog.auth('WebAuthCallbackHandler: Tokens stored successfully');

      // Clear pending auth
      await _pendingStorage.clearPendingAuth();

      // Clean up URL
      platform.clearUrlParams();

      return AuthCallbackSuccess(serverId: pending.serverId, tokens: tokens);
    } on Object catch (e) {
      DebugLog.error('WebAuthCallbackHandler: Token exchange failed: $e');
      await _pendingStorage.clearPendingAuth();
      platform.clearUrlParams();
      return AuthCallbackFailure(
        error: 'Token exchange failed',
        description: e.toString(),
      );
    }
  }

  /// Exchange authorization code for tokens using PKCE
  Future<OidcAuthTokenResponse> _exchangeCodeForTokens({
    required String code,
    required String codeVerifier,
    required String clientId,
    required String redirectUrl,
    required String tokenEndpoint,
  }) async {
    final url = Uri.parse(tokenEndpoint);
    final headers = {'Content-Type': 'application/x-www-form-urlencoded'};

    // Build the token request body with PKCE
    final bodyParams = {
      'grant_type': 'authorization_code',
      'code': code,
      'redirect_uri': redirectUrl,
      'client_id': clientId,
      'code_verifier': codeVerifier,
    };
    final body = bodyParams.entries
        .map(
          (e) =>
              '${Uri.encodeComponent(e.key)}=${Uri.encodeComponent(e.value)}',
        )
        .join('&');

    DebugLog.auth(
      'WebAuthCallbackHandler: POSTing to token endpoint: $tokenEndpoint',
    );

    // Record request for Network Inspector
    final requestId = _inspector?.recordRequest(
      method: 'POST',
      uri: url,
      headers: headers,
      body: body,
    );

    try {
      final response = await http
          .post(url, headers: headers, body: body)
          .timeout(HttpConfig.oidcTimeout);

      // Record response for Network Inspector
      if (requestId != null) {
        _inspector?.recordResponse(
          requestId: requestId,
          statusCode: response.statusCode,
          headers: response.headers,
          body: response.body,
        );
      }

      if (response.statusCode == 200) {
        final tokenData = json.decode(response.body) as Map<String, dynamic>;
        DebugLog.auth('WebAuthCallbackHandler: Token exchange successful');

        // Calculate expiration
        final expiresIn = tokenData['expires_in'] as int? ?? 3600;
        final expiration = DateTime.now().add(Duration(seconds: expiresIn));

        return OidcAuthTokenResponse(
          idToken: tokenData['id_token'] as String? ?? '',
          accessToken: tokenData['access_token'] as String,
          accessTokenExpiration: expiration,
          refreshToken: tokenData['refresh_token'] as String? ?? '',
        );
      } else {
        DebugLog.error(
          // ignore: lines_longer_than_80_chars (auto-documented)
          'WebAuthCallbackHandler: Token endpoint returned ${response.statusCode}',
        );
        DebugLog.error('WebAuthCallbackHandler: Response: ${response.body}');

        // Try to extract error from response
        try {
          final errorData = json.decode(response.body) as Map<String, dynamic>;
          final errorCode = errorData['error'] as String?;
          final errorDesc = errorData['error_description'] as String?;
          throw Exception(
            '${errorCode ?? 'token_error'}: ${errorDesc ?? response.body}',
          );
        } on Object catch (_) {
          throw Exception('Token endpoint returned ${response.statusCode}');
        }
      }
    } on Object catch (e) {
      // Record error for Network Inspector
      if (requestId != null) {
        _inspector?.recordError(requestId: requestId, error: e.toString());
      }
      rethrow;
    }
  }
}

/// Exception thrown when web auth redirect is initiated.
///
/// This is not an error - it signals that the browser is redirecting
/// to the OIDC provider and the app will reload at the callback URL.
class OidcWebRedirectException implements Exception {
  OidcWebRedirectException(this.serverId);

  /// The server ID we're authenticating to
  final String serverId;

  @override
  String toString() =>
      'OidcWebRedirectException: Redirecting to OIDC provider for $serverId';
}
