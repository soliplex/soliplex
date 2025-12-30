import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';
import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/auth/mobile_auth_provider.dart';
import 'package:soliplex_frontend/core/auth/web_auth_provider.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';
import 'package:soliplex_frontend/core/providers/config_provider.dart';
import 'package:soliplex_frontend/core/state/app_state.dart';
import 'package:soliplex_frontend/core/storage/secure_pending_storage.dart';
import 'package:soliplex_frontend/core/storage/secure_token_storage.dart';

/// Sentinel value indicating no authentication token is available.
///
/// Returned by [createTokenProvider] when:
/// - Not authenticated (no active session)
/// - Token expired and refresh failed
/// - Any error during token retrieval
///
/// Consumers should treat this as "unauthenticated" - the backend will
/// return 401 if authentication is required.
const noAuthToken = '';

/// Provider for FlutterSecureStorage instance.
///
/// Shared by [tokenStorageProvider] and [pendingStorageProvider].
final secureStorageProvider = Provider<FlutterSecureStorage>((ref) {
  return const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  );
});

/// Provider for token storage.
///
/// Uses platform-specific secure storage via [secureStorageProvider].
final tokenStorageProvider = Provider<TokenStorage>((ref) {
  final storage = ref.watch(secureStorageProvider);
  return SecureTokenStorage(storage: storage);
});

/// Provider for web auth pending storage.
///
/// Persists server ID between browser redirect and callback.
final pendingStorageProvider = Provider<WebAuthPendingStorage>((ref) {
  final storage = ref.watch(secureStorageProvider);
  return SecurePendingStorage(storage: storage);
});

/// Provider for FlutterAppAuth instance.
///
/// Only used on mobile platforms (iOS, Android, macOS).
final appAuthProvider = Provider<FlutterAppAuth>((ref) {
  return const FlutterAppAuth();
});

/// Provider for platform-appropriate AuthProvider.
///
/// Platform selection:
/// - Web: [WebAuthProvider] (backend-mediated OAuth)
/// - iOS, Android, macOS: [MobileAuthProvider] (PKCE via flutter_appauth)
/// - Windows, Linux: [WebAuthProvider] (backend-mediated OAuth)
final authProviderProvider = Provider<AuthProvider>((ref) {
  final tokenStorage = ref.watch(tokenStorageProvider);
  final httpClient = ref.watch(httpClientProvider);

  if (kIsWeb) {
    return _createWebAuthProvider(ref, tokenStorage, httpClient);
  }

  if (Platform.isIOS || Platform.isAndroid || Platform.isMacOS) {
    return _createMobileAuthProvider(ref, tokenStorage, httpClient);
  }

  // Windows and Linux use web auth (backend-mediated)
  return _createWebAuthProvider(ref, tokenStorage, httpClient);
});

WebAuthProvider _createWebAuthProvider(
  Ref ref,
  TokenStorage tokenStorage,
  http.Client httpClient,
) {
  final config = ref.watch(configProvider);
  final pendingStorage = ref.watch(pendingStorageProvider);

  return WebAuthProvider(
    baseUrl: config.baseUrl,
    tokenStorage: tokenStorage,
    pendingStorage: pendingStorage,
    httpClient: httpClient,
  );
}

MobileAuthProvider _createMobileAuthProvider(
  Ref ref,
  TokenStorage tokenStorage,
  http.Client httpClient,
) {
  final appAuth = ref.watch(appAuthProvider);

  return MobileAuthProvider(
    tokenStorage: tokenStorage,
    appAuth: appAuth,
    httpClient: httpClient,
  );
}

// ============================================================================
// App State - Authentication lifecycle state
// ============================================================================

/// Notifier for application authentication state.
///
/// Manages the auth lifecycle:
/// - NoServer: Initial state, no server configured
/// - NeedsAuth: Server configured, providers available
/// - Authenticating: Login in progress
/// - Ready: Authenticated and ready (includes config for token operations)
/// - Error: Auth error occurred
class AppStateNotifier extends Notifier<AppState> {
  @override
  AppState build() {
    return const AppStateNoServer();
  }

  /// Sets up the server and transitions to NeedsAuth state.
  ///
  /// Call this after fetching auth providers from the backend.
  void setNeedsAuth({
    required String serverId,
    required List<OIDCAuthSystem> providers,
  }) {
    state = AppStateNeedsAuth(serverId: serverId, providers: providers);
  }

  /// Begins authentication.
  ///
  /// Transitions to Authenticating state.
  /// Call [setAuthenticated] on success or [setError] on failure.
  void beginAuth(String serverId) {
    state = AppStateAuthenticating(serverId: serverId);
  }

  /// Completes authentication successfully.
  ///
  /// Transitions to Ready state with config for token operations.
  void setAuthenticated({
    required String serverId,
    required SsoConfig config,
    UserInfo? user,
  }) {
    state = AppStateReady(serverId: serverId, config: config, user: user);
  }

  /// Sets an error state.
  void setError({required String message, String? serverId}) {
    state = AppStateError(message: message, serverId: serverId);
  }

  /// Logs out and returns to NeedsAuth state.
  void loggedOut({
    required String serverId,
    required List<OIDCAuthSystem> providers,
  }) {
    state = AppStateNeedsAuth(serverId: serverId, providers: providers);
  }

  /// Clears all state and returns to NoServer.
  void reset() {
    state = const AppStateNoServer();
  }
}

/// Provider for application auth UI state.
final appStateProvider =
    NotifierProvider<AppStateNotifier, AppState>(AppStateNotifier.new);

// ============================================================================
// Token Provider - Bridges auth to HTTP transport
// ============================================================================

/// Typedef for token provider function used by HttpTransport.
typedef TokenProviderFn = Future<String> Function();

/// Creates a token provider function that retrieves valid tokens.
///
/// Reads auth config from [appStateProvider] when in Ready state.
///
/// Returns [noAuthToken] if:
/// - Not in Ready state (not authenticated)
/// - Token expired and refresh failed
/// - Any error during token retrieval
TokenProviderFn createTokenProvider(Ref ref) {
  return () async {
    final appState = ref.read(appStateProvider);

    switch (appState) {
      case AppStateReady(:final serverId, :final config):
        final authProvider = ref.read(authProviderProvider);

        try {
          final result = await authProvider.getValidToken(serverId, config);

          switch (result) {
            case Authenticated(:final token):
              return token.accessToken;
            case NoToken():
            case TokenExpired():
            case RefreshFailed():
            case StorageUnavailable():
              return noAuthToken;
          }
        } on AuthError catch (e) {
          // Transient auth errors (network, server) - return no token
          // so the request proceeds unauthenticated (backend returns 401).
          debugPrint('Auth error in token provider: $e');
          return noAuthToken;
        }
      // No generic Exception catch: getValidToken returns AuthResult for
      // expected outcomes and throws AuthError for transient failures.
      // Any other exception indicates a bug that should propagate.
      case AppStateNoServer():
      case AppStateNeedsAuth():
      case AppStateAuthenticating():
      case AppStateError():
        return noAuthToken;
    }
  };
}
