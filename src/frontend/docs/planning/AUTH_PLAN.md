# Authentication Implementation Plan

**Branch:** `feature/auth-implementation`

## Overview

Implement OIDC authentication for the Soliplex Flutter frontend with platform-specific flows (backend-mediated for web, PKCE for native) and multi-server support.

## Architecture Decision: Domain Placement

Based on Clean Architecture principles (blacksmith consultation):

### soliplex_client (Pure Dart)

**Domain Models:**

- `AuthToken` - Access token, refresh token, expiry, ID token
- `UserInfo` - User ID, email, name
- `OIDCAuthSystem` - Wire format from `GET /api/login` (provider list)
- `SsoConfig` - Full OIDC config after discovery

**Port Interfaces:**

- `AuthProvider` - Get valid token, login, logout, get user
- `TokenStorage` - Read/write/delete tokens per server

**Rationale:** Domain doesn't know about Flutter. API client uses AuthProvider interface. Implementations live in Flutter layer.

### Flutter App (lib/)

**Implementations:**

- `WebAuthProvider` implements AuthProvider (url_launcher, backend-mediated)
- `MobileAuthProvider` implements AuthProvider (flutter_appauth, PKCE)
- `SecureTokenStorage` implements TokenStorage (flutter_secure_storage)
- `SecureSsoStorage` - SSO config persistence per server

**State & UI:**

- `AppState` sealed class (NoServer, NeedsAuth, Authenticating, Ready, Error)
- Auth providers (Riverpod)
- Router guards
- Login screen, callback screen

## Files to Create

### soliplex_client Package

```text
packages/soliplex_client/lib/src/
├── auth/
│   ├── auth_token.dart           # AuthToken model
│   ├── user_info.dart            # UserInfo model
│   ├── oidc_auth_system.dart     # OIDCAuthSystem (from /api/login)
│   ├── sso_config.dart           # SsoConfig (expanded after discovery)
│   ├── auth_error.dart           # Sealed AuthError types
│   ├── auth_provider.dart        # AuthProvider interface
│   └── token_storage.dart        # TokenStorage interface
└── api/
    └── soliplex_api.dart         # MODIFY: Add getLoginProviders(), inject AuthProvider
```

### Flutter App

```text
lib/core/
├── auth/
│   ├── web_auth_provider.dart        # WebAuthProvider implementation
│   ├── mobile_auth_provider.dart     # MobileAuthProvider implementation
│   ├── secure_token_storage.dart     # SecureTokenStorage implementation
│   ├── secure_sso_storage.dart       # SSO config persistence per server
│   ├── secure_storage_gateway.dart   # Platform storage abstraction
│   └── oidc_discovery.dart           # OIDC discovery service
├── services/
│   └── secure_storage_service.dart   # Platform-specific storage (Keychain/EncryptedSharedPrefs/localStorage)
├── state/
│   └── app_state.dart                # Sealed AppState classes
└── providers/
    ├── auth_providers.dart           # Auth-related Riverpod providers
    └── api_provider.dart             # MODIFY: Inject AuthProvider into SoliplexApi

lib/features/
├── login/
│   ├── login_screen.dart             # Server selection + provider selection
│   └── auth_callback_screen.dart     # Handle OAuth callback (web)
└── settings/
    └── settings_screen.dart          # MODIFY: Add logout

lib/core/router/
    └── app_router.dart               # MODIFY: Add auth guards, login route, callback route
```

## Implementation Steps (with Commits)

---

### Commit 1: Domain models in soliplex_client ✅

**Files:**

- `packages/soliplex_client/lib/src/auth/auth_token.dart`
- `packages/soliplex_client/lib/src/auth/user_info.dart`
- `packages/soliplex_client/lib/src/auth/oidc_auth_system.dart`
- `packages/soliplex_client/lib/src/auth/sso_config.dart`
- `packages/soliplex_client/lib/src/auth/auth_error.dart`
- `packages/soliplex_client/lib/soliplex_client.dart` (export)
- Tests for all models

**Details:**

1. AuthToken - accessToken, refreshToken, expiresAt, idToken, `isExpired`/`needsRefresh` getters
2. UserInfo - id, email, name
3. OIDCAuthSystem - id, title, serverUrl, clientId, scope, fromJson
4. SsoConfig - full OIDC endpoints, reference to OIDCAuthSystem
5. AuthError - sealed class (Cancelled, NetworkError, TokenExpired, etc.)

---

### Commit 2: Port interfaces in soliplex_client ✅

**Files:**

- `packages/soliplex_client/lib/src/auth/auth_provider.dart`
- `packages/soliplex_client/lib/src/auth/token_storage.dart`
- `packages/soliplex_client/lib/soliplex_client.dart` (export)

**Details:**

1. AuthProvider interface:

   ```dart
   abstract interface class AuthProvider {
     Future<Result<AuthToken, AuthError>> getValidToken(String serverId);
     Future<Result<AuthToken, AuthError>> login(String serverId, SsoConfig config);
     Future<Result<void, AuthError>> logout(String serverId);
     Future<Result<UserInfo?, AuthError>> getCurrentUser(String serverId);
   }
   ```

2. TokenStorage interface:

   ```dart
   abstract interface class TokenStorage {
     Future<AuthToken?> read(String serverId);
     Future<void> write(String serverId, AuthToken token);
     Future<void> delete(String serverId);
   }
   ```

---

### Commit 3: SoliplexApi auth integration ✅

**Files:**

- `packages/soliplex_client/lib/src/http/http_transport.dart` (modify - add TokenProvider)
- `lib/core/providers/api_provider.dart` (modify - wire stub TokenProvider)
- Tests

**Details:**

1. Add `TokenProvider` typedef for auth header injection
2. HttpTransport accepts required `tokenProvider` callback
3. Auth header only added when token is non-empty

---

### Commit 4: SecureTokenStorage implementation ✅

**Files:**

- `pubspec.yaml` (add flutter_secure_storage)
- `lib/core/storage/secure_token_storage.dart`
- Tests

**Details:**

1. SecureTokenStorage implements TokenStorage using flutter_secure_storage
2. Per-server key prefixing (`auth_token_{serverId}`)
3. JSON serialization/deserialization of AuthToken

**Note:** Merged original commits 4+5. Dropped SecureSsoStorage per YAGNI - PKCE state and SsoConfig held in-memory by auth provider.

---

### Commit 5: OIDC discovery service ✅

**Files:**

- `packages/soliplex_client/lib/src/auth/oidc_discovery_service.dart`
- Tests

**Details:**

1. OidcDiscoveryService in soliplex_client (pure Dart, no Flutter)
2. Fetches `{serverUrl}/.well-known/openid-configuration`
3. Type-safe string extraction with AuthErrorConfiguration on wrong types
4. Returns SsoConfig combining discovery endpoints with OIDCAuthSystem

---

### Commit 6: Mobile auth provider (PKCE) ✅

**Files:**

- `lib/core/auth/mobile_auth_provider.dart`
- `pubspec.yaml` (add flutter_appauth)
- Platform configs (Android, iOS, macOS)
- Tests

**Details:**

1. MobileAuthProvider implements AuthProvider
2. Uses flutter_appauth for PKCE flow (iOS, Android, macOS only)
3. Token refresh via flutter_appauth.token()
4. Platform configurations for deep links
5. RefreshResult sealed class for type-safe refresh handling

**Note:** flutter_appauth only supports iOS, Android, macOS. Windows and Linux use WebAuthProvider.

---

### Commit 7: Web auth provider (backend-mediated) ✅

**Files:**

- `lib/core/auth/web_auth_provider.dart`
- `pubspec.yaml` (add url_launcher)
- Tests

**Details:**

1. WebAuthProvider implements AuthProvider for web, Windows, Linux
2. Platform-specific callback handling:
   - Web: Browser redirect with query params
   - Desktop (Windows/Linux): Local HTTP server on 127.0.0.1
3. CSRF state generation and validation
4. Token extraction from query params (backend limitation)
5. Token refresh via HTTP POST to backend

**Platform selection logic:**

```dart
if (kIsWeb) return WebAuthProvider(...);
if (Platform.isIOS || Platform.isAndroid || Platform.isMacOS) {
  return MobileAuthProvider(...);
}
return WebAuthProvider(...);  // Windows, Linux
```

---

### Commit 8: App state machine ✅

**Files:**

- `lib/core/state/app_state.dart`
- Tests

**Details:**

1. Sealed AppState classes:
   - AppStateNoServer
   - AppStateNeedsAuth
   - AppStateAuthenticating
   - AppStateReady
   - AppStateError

---

### Commit 9: Auth providers (Riverpod) ✅

**Files:**

- `lib/core/providers/auth_providers.dart`
- `lib/core/providers/api_provider.dart` (modify)
- `lib/core/storage/secure_pending_storage.dart`
- Tests

**Details:**

1. secureStorageProvider
2. tokenStorageProvider
3. pendingStorageProvider (for web auth)
4. authProviderProvider (platform-aware factory)
5. appStateProvider (Notifier with internal session state)
6. Wire TokenProvider to AuthProvider.getValidToken()

**Note:** Added SecurePendingStorage for WebAuthProvider's pending server state.

---

### Commit 10: Router auth guards ✅

**Files:**

- `lib/core/router/app_router.dart` (modify)
- `lib/core/router/router_notifier.dart`
- Tests

**Details:**

1. Add `/login` route
2. Add `/auth/callback` route (web)
3. Add redirect logic based on AppState
4. RouterNotifier listens to appStateProvider

---

### Commit 11: Login screen and auth orchestrator refactoring ✅

**Files:**

- `lib/features/login/login_screen.dart`
- `lib/core/auth/auth_orchestrator.dart`
- `lib/core/providers/auth_providers.dart` (refactored)
- `lib/core/providers/api_provider.dart` (added serverIdProvider)
- `test/helpers/auth_test_helpers.dart` (consolidated fixtures)
- Tests

**Details:**

1. Server URL input with validation
2. Probe server for providers via AuthOrchestrator
3. Provider selection UI with Material Design
4. Initiate auth flow, handle redirect/success/failure

**Architectural improvements (blacksmith review):**

1. **AppStateNotifier refactored to thin state container** - Removed `probeServer()` and `login()` methods; UI now calls orchestrator directly and updates state via notifier methods
2. **serverIdProvider added** - Decouples URL building from full AppState, improving caching
3. **TestAppStateNotifier simplified** - No longer needs `initializeOrchestrator()` call
4. **MockAuthOrchestrator consolidated** - Single hand-rolled mock with optional params, fail-fast StateError on unconfigured methods
5. **Test fixtures consolidated** - All auth fixtures in `auth_test_helpers.dart`
6. **setError preserves providers** - Automatic provider preservation for retry UX, with comprehensive test coverage

---

### Commit 12: Auth callback screen (web)

**Files:**

- `lib/features/login/auth_callback_screen.dart`
- Tests

**Details:**

1. Extract tokens from URL
2. Validate CSRF state
3. Clear URL params immediately
4. Store tokens, navigate to app

---

### Commit 13: Logout and settings integration

**Files:**

- `lib/features/settings/settings_screen.dart` (modify)
- Tests

**Details:**

1. Add logout button
2. Server info display
3. Current user display

## Final Architecture

After implementation and architectural review (blacksmith consultation), the auth system uses a **two-transport architecture** to break circular dependencies and properly separate authenticated vs unauthenticated concerns.

### Provider Dependency Graph

```text
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 1: Base Infrastructure (unauthenticated)                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  observableClientProvider                                           │
│       │                                                             │
│       ▼                                                             │
│  baseHttpTransportProvider (no token injection)                     │
│       │                                                             │
│       ├──► oidcDiscoveryServiceProvider                             │
│       │              │                                              │
│       │              ▼                                              │
│       └──► authOrchestratorProvider ◄── authApiProvider             │
│                      │                                              │
├──────────────────────┼──────────────────────────────────────────────┤
│  LAYER 2: Auth State │                                              │
├──────────────────────┼──────────────────────────────────────────────┤
│                      ▼                                              │
│            appStateProvider (watches authOrchestratorProvider)      │
│                      │                                              │
├──────────────────────┼──────────────────────────────────────────────┤
│  LAYER 3: Authenticated Services                                    │
├──────────────────────┼──────────────────────────────────────────────┤
│                      ▼                                              │
│            createTokenProvider (reads appStateProvider)             │
│                      │                                              │
│                      ▼                                              │
│  observableClientProvider ──► httpTransportProvider (with tokens)   │
│                                        │                            │
│                                        ▼                            │
│                                   apiProvider                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

**Two HTTP Transports:**

| Provider | Token Injection | Use Case |
|----------|-----------------|----------|
| `baseHttpTransportProvider` | None | OIDC discovery, server probing, token refresh |
| `httpTransportProvider` | Bearer token | All authenticated API calls |

**Why this matters:** OIDC discovery and server probing happen *before* authentication. Routing them through an authenticated transport would create a circular dependency:

```text
httpTransportProvider → tokenProvider → appStateProvider
    → authOrchestratorProvider → oidcDiscoveryServiceProvider
    → httpTransportProvider (CYCLE!)
```

The `baseHttpTransportProvider` breaks this cycle by providing unauthenticated HTTP without depending on auth state.

**HttpTransport Changes:**

```dart
// Token provider is now optional with a no-op default
HttpTransport({
  required SoliplexHttpClient client,
  TokenProvider tokenProvider = noTokenProvider,  // Default: no auth
  this.defaultTimeout = const Duration(seconds: 30),
});

// No-op token provider for unauthenticated requests
Future<String> noTokenProvider() async => '';
```

### State Machine

```dart
sealed class AppState {
  const AppState();
}

final class AppStateNoServer extends AppState { }
final class AppStateProbing extends AppState { serverId }
final class AppStateNeedsAuth extends AppState { serverId, providers }
final class AppStateAuthenticating extends AppState { serverId, providers }
final class AppStateReady extends AppState { serverId, config, user }
final class AppStateError extends AppState { message, serverId?, providers }
```

**State Transitions:**

```text
NoServer ──probe──► Probing ──success──► NeedsAuth ──login──► Authenticating
    │                  │                     │                      │
    │                  │ failure             │ error                │ success
    │                  ▼                     ▼                      ▼
    │               Error ◄────────────── Error                   Ready
    │                  │                                            │
    │                  │ retry                                      │ logout
    └──────────────────┴────────────────────────────────────────────┘
```

### Auth Orchestrator

Pure Dart coordinator (no Flutter imports) that returns result types:

```dart
class AuthOrchestrator {
  Future<ProbeResult> probeServer(String serverUrl);
  Future<LoginAttemptResult> login(OIDCAuthSystem authSystem, String serverId);
}

sealed class ProbeResult { }
final class ProbeSuccess extends ProbeResult { providers }
final class ProbeFailure extends ProbeResult { message }

sealed class LoginAttemptResult { }
final class LoginAttemptSuccess extends LoginAttemptResult { config, user }
final class LoginAttemptRedirect extends LoginAttemptResult { }  // Web flow
final class LoginAttemptFailure extends LoginAttemptResult { message }
```

### Platform Selection

```dart
final authProviderProvider = Provider<AuthProvider>((ref) {
  if (kIsWeb) return WebAuthProvider(...);
  if (Platform.isIOS || Platform.isAndroid || Platform.isMacOS) {
    return MobileAuthProvider(...);  // PKCE via flutter_appauth
  }
  return WebAuthProvider(...);  // Windows, Linux use backend-mediated
});
```

### Test Infrastructure

Shared fixtures in `test/helpers/auth_test_helpers.dart`:

```dart
// Fixtures
const testAuthSystem = OIDCAuthSystem(id: 'keycloak', ...);
const testSsoConfig = SsoConfig(authSystem: testAuthSystem, ...);
const testUser = UserInfo(id: 'user-123', email: 'user@example.com');
const testProviders = [testAuthSystem];

// Far-future expiration for test tokens
final _testTokenExpiration = DateTime.utc(2099);
final testToken = AuthToken(accessToken: '...', expiresAt: _testTokenExpiration);

// Test notifier - starts in specific state for UI tests
class TestAppStateNotifier extends AppStateNotifier {
  TestAppStateNotifier(this._initialState);
  final AppState _initialState;

  @override
  AppState build() => _initialState;  // Simplified - no orchestrator needed
}

// Mock orchestrator - configure only what you need, fail-fast on unconfigured
class MockAuthOrchestrator implements AuthOrchestrator {
  MockAuthOrchestrator({this.probeResult, this.loginResult});

  final ProbeResult? probeResult;
  final LoginAttemptResult? loginResult;

  @override
  Future<ProbeResult> probeServer(String serverUrl) async {
    if (probeResult == null) {
      throw StateError('MockAuthOrchestrator.probeServer() not configured');
    }
    return probeResult!;
  }

  @override
  Future<LoginAttemptResult> login(...) async {
    if (loginResult == null) {
      throw StateError('MockAuthOrchestrator.login() not configured');
    }
    return loginResult!;
  }
}
```

### Files Summary

**Core Auth:**
- `lib/core/auth/auth_orchestrator.dart` - Coordinates auth flows (pure Dart)
- `lib/core/auth/mobile_auth_provider.dart` - PKCE via flutter_appauth
- `lib/core/auth/web_auth_provider.dart` - Backend-mediated OAuth
- `lib/core/state/app_state.dart` - Sealed state hierarchy

**Providers:**
- `lib/core/providers/auth_providers.dart` - All auth providers + AppStateNotifier
- `lib/core/providers/api_provider.dart` - Dual transport architecture

**Router:**
- `lib/core/router/app_router.dart` - Auth guards, login/callback routes
- `lib/core/router/router_notifier.dart` - Bridges Riverpod to GoRouter

**UI:**
- `lib/features/login/login_screen.dart` - Server probe + provider selection
- `lib/features/login/auth_callback_screen.dart` - Web OAuth callback (stub)

## Security Measures (Minimal Viable)

- **CSRF state validation**: Generate random state before redirect, validate on callback
- **Clear URL params immediately**: Before processing tokens (minimize exposure)
- **Token expiry checking**: Refresh 5 minutes before expiry
- **Per-server isolation**: Independent tokens/config per server

## Key Integration Points

| File | Change |
|------|--------|
| `packages/soliplex_client/lib/src/api/soliplex_api.dart` | Add AuthProvider injection, getLoginProviders() |
| `lib/core/providers/api_provider.dart` | Wire AuthProvider into API |
| `lib/core/router/app_router.dart` | Auth guards, login/callback routes |
| `pubspec.yaml` | Add auth dependencies |

## Testing Strategy

- Unit tests for AuthToken, SsoConfig, UserInfo models
- Unit tests for TokenStorage, SsoStorage operations
- Mock AuthProvider for API client tests
- Widget tests for login flow
- Integration tests for callback handling

## Dependencies on Backend

- `GET /api/login` - Returns List<OIDCAuthSystem>
- `GET /api/login/{provider}?return_to=...` - Initiates backend-mediated OAuth (web)
- `GET /api/auth/{provider}` - OAuth callback, redirects with tokens
- `GET /api/user_info` - Returns authenticated user info (note: underscore, not hyphen)

## Backend Security Notes

**Current state (as of 2024-12-29):**

The backend (`src/soliplex/src/soliplex/views/auth.py`) returns tokens via **query parameters**:

```python
return_to += f"?token={access_token}"
return_to += f"&refresh_token={refresh_token}"
return_to += f"&expires_in={expires_in}"
return_to += f"&refresh_expires_in={refresh_expires_in}"
```

**Security implications:**

| Concern | Query Params (current) | Fragments (recommended) |
|---------|----------------------|------------------------|
| Server logs | ✗ Exposed | ✓ Not sent to server |
| Browser history | ✗ Stored | ✓ Not stored |
| Referer header | ✗ Leaks to external resources | ✓ Protected |

**Recommendation for future improvement:**

Change backend to use URL fragments instead:

```python
return_to += f"#access_token={access_token}&refresh_token=..."
```

**Current decision:** Proceed with query params (current backend behavior). Frontend will clear URL params immediately after extraction to minimize exposure window.

**Additional backend observations:**

- No explicit redirect_uri whitelist (potential open redirect risk)
- State parameter handled by authlib via `authorize_state`
- No timeout for abandoned auth flows

## Open Questions

None - design is complete based on reference documentation and blacksmith consultations.
