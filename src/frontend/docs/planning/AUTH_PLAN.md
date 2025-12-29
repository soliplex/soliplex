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

### Commit 2: Port interfaces in soliplex_client

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

### Commit 3: SoliplexApi auth integration

**Files:**

- `packages/soliplex_client/lib/src/api/soliplex_api.dart` (modify)
- Tests

**Details:**

1. Add `Future<List<OIDCAuthSystem>> getLoginProviders()` method
2. Constructor accepts optional AuthProvider
3. Methods call `authProvider.getValidToken()` before authenticated requests

---

### Commit 4: Flutter secure storage service

**Files:**

- `lib/core/services/secure_storage_service.dart`
- `pubspec.yaml` (add flutter_secure_storage)
- Tests

**Details:**

1. Abstract SecureStorageService interface
2. NativeSecureStorageService (flutter_secure_storage with Keychain/EncryptedSharedPrefs)
3. WebSecureStorageService (localStorage)
4. SecureStorageFactory for platform detection

---

### Commit 5: Auth storage implementations

**Files:**

- `lib/core/auth/secure_storage_gateway.dart`
- `lib/core/auth/secure_token_storage.dart`
- `lib/core/auth/secure_sso_storage.dart`
- Tests

**Details:**

1. SecureStorageGateway - thin wrapper with read/write/delete
2. SecureTokenStorage - implements TokenStorage, per-server keys
3. SecureSsoStorage - per-server SSO config persistence

---

### Commit 6: OIDC discovery service

**Files:**

- `lib/core/auth/oidc_discovery.dart`
- Tests

**Details:**

1. Fetch OIDC `.well-known/openid-configuration`
2. Build SsoConfig from OIDCAuthSystem + discovery metadata

---

### Commit 7: Mobile auth provider (PKCE)

**Files:**

- `lib/core/auth/mobile_auth_provider.dart`
- `pubspec.yaml` (add flutter_appauth)
- Platform configs (Android, iOS, macOS)
- Tests

**Details:**

1. OidcMobileAuthProvider implements AuthProvider
2. Uses flutter_appauth for PKCE flow
3. Token refresh via flutter_appauth.token()
4. Platform configurations for deep links

---

### Commit 8: Web auth provider (backend-mediated)

**Files:**

- `lib/core/auth/web_auth_provider.dart`
- `pubspec.yaml` (add url_launcher, crypto)
- Tests

**Details:**

1. OidcWebAuthProvider implements AuthProvider
2. Backend-mediated flow via url_launcher
3. CSRF state generation and validation
4. Token refresh via HTTP POST

---

### Commit 9: App state machine

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

### Commit 10: Auth providers (Riverpod)

**Files:**

- `lib/core/providers/auth_providers.dart`
- `lib/core/providers/api_provider.dart` (modify)
- Tests

**Details:**

1. secureStorageProvider
2. tokenStorageProvider
3. ssoStorageProvider
4. authProviderProvider (platform-aware factory)
5. appStateProvider (AsyncNotifier)
6. Inject AuthProvider into SoliplexApi

---

### Commit 11: Router auth guards

**Files:**

- `lib/core/router/app_router.dart` (modify)

**Details:**

1. Add `/login` route
2. Add `/auth/callback` route (web)
3. Add redirect logic based on AppState
4. RouterNotifier listens to appStateProvider

---

### Commit 12: Login screen

**Files:**

- `lib/features/login/login_screen.dart`
- Tests

**Details:**

1. Server URL input
2. Probe server for providers
3. Provider selection UI
4. Initiate auth flow

---

### Commit 13: Auth callback screen (web)

**Files:**

- `lib/features/login/auth_callback_screen.dart`
- Tests

**Details:**

1. Extract tokens from URL
2. Validate CSRF state
3. Clear URL params immediately
4. Store tokens, navigate to app

---

### Commit 14: Logout and settings integration

**Files:**

- `lib/features/settings/settings_screen.dart` (modify)
- Tests

**Details:**

1. Add logout button
2. Server info display
3. Current user display

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
- `GET /api/user-info` - Returns authenticated user info

## Open Questions

None - design is complete based on reference documentation and blacksmith consultations.
