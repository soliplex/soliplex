import 'package:soliplex/core/auth/callback_params.dart';
import 'package:soliplex/core/auth/oidc_auth_token_response.dart';
import 'package:soliplex/core/auth/secure_token_storage.dart';
import 'package:soliplex/core/auth/web_auth_callback_stub.dart'
    if (dart.library.js_interop) 'web_auth_callback_web.dart'
    as platform;
import 'package:soliplex/core/auth/web_auth_pending_storage.dart';
import 'package:soliplex/core/services/secure_storage_service.dart';
import 'package:soliplex/core/utils/debug_log.dart';

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

/// Handles the OIDC authorization callback for web.
///
/// Supports two callback flows:
/// 1. **Backend-mediated** (web): Tokens are passed directly in URL params
/// 2. **PKCE** (legacy): Authorization code requires exchange (not used on web)
///
/// When the browser redirects back from authentication:
/// 1. Extracts tokens or error from the URL
/// 2. Validates we have a pending auth session
/// 3. Stores the tokens
/// 4. Returns the server ID for navigation
class WebAuthCallbackHandler {
  WebAuthCallbackHandler({
    required WebAuthPendingStorage pendingStorage,
    required SecureTokenStorage tokenStorage,
    required this.secureStorageService,
  }) : _pendingStorage = pendingStorage,
       _tokenStorage = tokenStorage;

  final WebAuthPendingStorage _pendingStorage;
  final SecureTokenStorage _tokenStorage;
  final SecureStorageService secureStorageService;

  /// Check if we're on an auth callback URL
  bool isAuthCallback() => platform.isAuthCallback();

  /// Get current URL path (for logging/debugging)
  String getCurrentPath() => platform.getCurrentPath();

  /// Process the auth callback.
  ///
  /// Returns [AuthCallbackSuccess] with server ID and tokens on success,
  /// [AuthCallbackFailure] on error, or [AuthCallbackNotDetected] if not on
  /// callback URL.
  Future<AuthCallbackResult> handleCallback() async {
    DebugLog.auth('WebAuthCallbackHandler: Checking for callback...');
    DebugLog.auth('WebAuthCallbackHandler: Current path: ${getCurrentPath()}');

    // First check cached params (captured at app startup before GoRouter
    // potentially modified the URL)
    final cachedParams = platform.getCachedCallbackParams();
    DebugLog.auth('WebAuthCallbackHandler: Cached params: $cachedParams');

    // Use cached params if available, otherwise check current URL
    CallbackParams params;
    if (cachedParams != null && cachedParams is! NoCallbackParams) {
      params = cachedParams;
      // Clear cached params after reading to prevent re-processing
      platform.clearCachedCallbackParams();
    } else if (isAuthCallback()) {
      params = platform.extractCallbackParams();
    } else {
      DebugLog.auth('WebAuthCallbackHandler: Not on callback URL');
      return AuthCallbackNotDetected();
    }

    DebugLog.auth('WebAuthCallbackHandler: Using params - $params');

    // Route to appropriate handler based on callback type
    switch (params) {
      case BackendMediatedCallbackParams():
        return _handleBackendMediatedCallback(params);
      case PkceCallbackParams():
        return _handlePkceCallback(params);
      case NoCallbackParams():
        DebugLog.auth('WebAuthCallbackHandler: No callback params found');
        return AuthCallbackNotDetected();
    }
  }

  /// Handle backend-mediated callback (tokens in URL).
  ///
  /// The backend has already exchanged the authorization code for tokens
  /// and redirected back with tokens as URL query parameters.
  Future<AuthCallbackResult> _handleBackendMediatedCallback(
    BackendMediatedCallbackParams params,
  ) async {
    DebugLog.auth('WebAuthCallbackHandler: Backend-mediated callback');

    // Check for error from backend
    if (params.hasError) {
      DebugLog.error('WebAuthCallbackHandler: Backend error: ${params.error}');
      await _pendingStorage.clearPendingAuth();
      platform.clearUrlParams();
      return AuthCallbackFailure(error: params.error!);
    }

    // Validate we have an access token
    if (params.accessToken == null) {
      DebugLog.error('WebAuthCallbackHandler: Missing access token');
      await _pendingStorage.clearPendingAuth();
      platform.clearUrlParams();
      return AuthCallbackFailure(error: 'Missing access token from server');
    }

    // Get pending auth to retrieve serverId
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

    // Calculate expiration
    final expiresIn = params.expiresIn ?? 3600;
    final expiration = DateTime.now().add(Duration(seconds: expiresIn));

    final tokens = OidcAuthTokenResponse(
      idToken: '', // Backend doesn't return id_token in URL redirect
      accessToken: params.accessToken!,
      accessTokenExpiration: expiration,
      refreshToken: params.refreshToken ?? '',
    );

    // Store tokens using server-specific keys for AuthManager compatibility
    DebugLog.auth(
      'WebAuthCallbackHandler: Storing tokens for server ${pending.serverId}',
    );
    DebugLog.auth(
      'WebAuthCallbackHandler: Access token length: '
      '${params.accessToken!.length}',
    );
    await secureStorageService.storeTokens(
      serverId: pending.serverId,
      accessToken: params.accessToken!,
      refreshToken: params.refreshToken,
      expiresAt: expiration,
    );

    // Also store in the legacy format for backward compatibility
    await _tokenStorage.setOidcAuthTokenResponse(tokens);
    DebugLog.auth('WebAuthCallbackHandler: Tokens stored successfully');

    // Verify storage
    final storedToken = await secureStorageService.getAccessToken(
      pending.serverId,
    );
    DebugLog.auth(
      'WebAuthCallbackHandler: Verification - stored token present: '
      '${storedToken != null}',
    );

    // Clear pending auth
    await _pendingStorage.clearPendingAuth();

    // Clean up URL
    platform.clearUrlParams();

    return AuthCallbackSuccess(serverId: pending.serverId, tokens: tokens);
  }

  /// Handle PKCE callback (authorization code in URL).
  ///
  /// This flow is not used on web (backend-mediated flow is used instead).
  /// On web, receiving a PKCE callback indicates a misconfiguration.
  Future<AuthCallbackResult> _handlePkceCallback(
    PkceCallbackParams params,
  ) async {
    DebugLog.auth('WebAuthCallbackHandler: PKCE callback (unexpected on web)');

    // Check for error from OIDC provider
    if (params.hasError) {
      DebugLog.error('WebAuthCallbackHandler: OIDC error: ${params.error}');
      await _pendingStorage.clearPendingAuth();
      platform.clearUrlParams();
      return AuthCallbackFailure(error: params.error!);
    }

    // PKCE flow is not supported on web - the backend should handle
    // the code exchange and redirect with tokens
    DebugLog.error(
      'WebAuthCallbackHandler: PKCE callback not supported on web. '
      'Backend should redirect with tokens.',
    );
    await _pendingStorage.clearPendingAuth();
    platform.clearUrlParams();
    return AuthCallbackFailure(
      error: 'Unsupported authentication flow',
      description:
          'Received authorization code instead of tokens. '
          'Please contact support.',
    );
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
