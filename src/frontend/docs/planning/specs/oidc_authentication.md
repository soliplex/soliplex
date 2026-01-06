# OIDC Authentication (AM7)

Cross-platform OIDC authentication using direct OIDC flow via `flutter_appauth`.

> **Implementation Note**: Keep this document updated as implementation progresses.
> If context is lost and work needs to resume, this document serves as the source of
> truth for decisions made and current status. Update the "Implementation Progress"
> section below after completing each slice.

## Overview

The app authenticates directly with the IdP (Keycloak) using `flutter_appauth`.
Backend provides IdP configuration but does not participate in the OAuth flow.

**Flow:**

1. Discover IdP configuration via `GET /api/login` → `{ server_url, client_id, scope }`
2. `flutter_appauth` handles full OAuth flow:
   - Opens system browser to IdP authorization endpoint
   - User authenticates with IdP
   - IdP redirects to app with authorization code
   - `flutter_appauth` exchanges code for tokens (PKCE handled automatically)
3. Store tokens securely (Keychain on iOS/macOS)
4. Add `Authorization: Bearer {token}` to API requests
5. Refresh tokens before expiry (direct to IdP token endpoint)

## MVP Scope

**In scope (MVP):**

- macOS (primary development/test platform)
- iOS

**Deferred (post-MVP):**

- Windows/Linux (loopback server complexity)
- Web (different security model, CORS complexity)

## Architecture: Core vs Frontend Boundary

`soliplex_client` (future: `soliplex_core`) must remain frontend-agnostic to support
swappable frontends (Flutter, CLI, potentially others). Both Flutter and CLI will use
OIDC authentication.

### Design Principle

**Core is a "dumb pipe"** that:

- Fetches auth configuration from the backend (menu of options)
- Attaches tokens to HTTP requests
- Does NOT know how tokens are obtained or refreshed

**Frontend handles:**

- Interpreting auth configuration (e.g., recognizing it as OIDC)
- Running platform-specific auth flows (flutter_appauth, device code, etc.)
- Token storage and refresh orchestration
- Providing tokens to core

### What Belongs in `soliplex_client`

| Component | Rationale |
|-----------|-----------|
| `AuthProviderConfig` | Pure data class describing backend's `/api/login` response. Agnostic to auth type. |
| `AuthenticatedHttpClient` | Decorator that injects `Authorization: Bearer` header. Pure Dart, no platform deps. |
| `fetchAuthProviders()` | API call to `/api/login`. Just fetches config, doesn't interpret it. |

**AuthProviderConfig** (explicit OIDC fields for MVP):

```dart
/// Auth provider configuration from /api/login.
@immutable
class AuthProviderConfig {
  const AuthProviderConfig({
    required this.id,
    required this.name,
    required this.serverUrl,
    required this.clientId,
    required this.scope,
  });

  final String id;
  final String name;
  final String serverUrl;
  final String clientId;
  final String scope;
}
```

> **YAGNI Note**: The original design proposed generic `type` + `metadata` fields
> for future extensibility (SAML, etc.). The implementation uses explicit OIDC
> fields since that's all we support. If non-OIDC providers are needed later,
> refactor to a sealed class hierarchy.

**AuthenticatedHttpClient** (single responsibility: add tokens, no retry):

```dart
/// Decorates HTTP client with Bearer token injection.
/// Does NOT handle 401 retry - that's the orchestration layer's job.
class AuthenticatedHttpClient implements SoliplexHttpClient {
  AuthenticatedHttpClient(this._inner, this._getToken);

  final SoliplexHttpClient _inner;
  final String? Function() _getToken;

  @override
  Future<HttpResponse> request(...) {
    final token = _getToken();
    final headers = token != null
        ? {...?existingHeaders, 'Authorization': 'Bearer $token'}
        : existingHeaders;
    return _inner.request(method, uri, headers: headers, ...);
  }
}
```

### What Stays in Flutter Frontend

| Component | Rationale |
|-----------|-----------|
| `OidcIssuer` | Frontend-specific interpretation of `AuthProviderConfig` for OIDC. |
| `AuthState` sealed class | State management is frontend-specific (Riverpod). CLI may use different patterns. |
| `authenticate()` | Uses `flutter_appauth`. CLI would use device code flow. |
| `AuthNotifier` | Riverpod-specific state management + 401 retry orchestration. |
| Token storage | `flutter_secure_storage` is platform-specific. |
| Refresh orchestration | When/how to refresh differs per frontend UX. |

### Naming Convention

Avoid `*Provider` suffix in `soliplex_client` to prevent confusion with Riverpod's
`Provider` terminology. Use inline function types:

```dart
// Preferred: inline type
final String? Function() _getToken;
```

### HTTP Decorator Order and Observability

**Wrapping hierarchy:** `Refreshing(Authenticated(Observable(Platform)))`

```dart
// 1. Platform client (innermost)
final platform = createPlatformClient();

// 2. Observable wraps Platform
final observable = ObservableHttpClient(client: platform, observers: [...]);

// 3. Authenticated wraps Observable
final authenticated = AuthenticatedHttpClient(client: observable, getToken: ...);

// 4. Refreshing wraps Authenticated (outermost)
final refreshing = RefreshingHttpClient(inner: authenticated, refresher: authNotifier);
```

**Call order for requests:**

```text
Caller
  ↓ refreshing.request()
Refreshing checks needsRefresh, proactively refreshes if needed
  ↓ authenticated.request()
Authenticated adds token to headers
  ↓ observable.request()
Observable logs request (WITH auth headers)
  ↓ platform.request()
Platform sends over wire
```

**Response order:**

```text
Platform receives response
  ↓
Observable logs response (sees 401s, all errors)
  ↓
Authenticated returns response
  ↓
Refreshing checks for 401, refreshes and retries ONCE if needed
  ↓
Caller
```

**Why this order:**

- Observer sees requests WITH auth headers (accurate logging)
- Observer sees all responses including 401s
- RefreshingHttpClient handles retry at the outermost layer
- Single retry limit prevents infinite loops (CWE-834)

### 401 Retry Architecture

**Key decision:** `AuthenticatedHttpClient` does NOT retry. It only adds tokens.
`RefreshingHttpClient` handles all refresh and retry logic as a separate decorator.

```text
1. Original request → Refreshing → Authenticated → Observable → Platform
2. 401 response     ← (observer sees this)
3. RefreshingHttpClient triggers refresh via TokenRefresher interface
4. Refresh request  → Observable → Platform (uses base client, not authenticated)
5. Refresh response ← (observer sees this)
6. RefreshingHttpClient retries original request (retried=true prevents loops)
7. Retry request    → Refreshing → Authenticated → Observable → Platform
8. Final response   ← (observer sees this)
```

**Observer sees all HTTP calls.** No visibility is lost.

```dart
// RefreshingHttpClient - HTTP decorator layer
class RefreshingHttpClient implements SoliplexHttpClient {
  final SoliplexHttpClient _inner;
  final TokenRefresher _refresher;
  Completer<bool>? _refreshInProgress;  // Dedupes concurrent refreshes

  Future<HttpResponse> request(...) async {
    await _refresher.refreshIfExpiringSoon();  // Proactive refresh
    return _executeWithRetry(..., retried: false);
  }

  Future<HttpResponse> _executeWithRetry(..., {required bool retried}) async {
    final response = await _inner.request(...);

    // On 401, attempt refresh and retry ONCE (CWE-834 prevention)
    if (response.statusCode == 401 && !retried) {
      if (await _tryRefreshOnce()) {
        return _executeWithRetry(..., retried: true);
      }
    }
    return response;
  }
}
```

**Security controls:**

- Single retry limit via `retried` flag prevents infinite 401→refresh→401 loops (CWE-834)
- Completer pattern deduplicates concurrent refresh attempts
- Refresh uses base HTTP client (not authenticated) to avoid refresh token loops

### Flow Diagram

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                          soliplex_client (core)                          │
│                                                                          │
│  Defines abstractions:                                                   │
│    • TokenRefresher (interface)                                          │
│    • String? Function() (token getter signature)                         │
│                                                                          │
│  fetchAuthProviders() ──► List<AuthProviderConfig>                       │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ RefreshingHttpClient                                               │  │
│  │   - Wraps AuthenticatedHttpClient                                  │  │
│  │   - Proactive refresh before requests when needsRefresh            │  │
│  │   - On 401: refresh via TokenRefresher, retry ONCE                 │  │
│  │   - Concurrent refresh deduplication via Completer                 │  │
│  │   - CWE-834: Single retry limit prevents infinite loops            │  │
│  │                                                                    │  │
│  │   Dependencies:                                                    │  │
│  │     inner: AuthenticatedHttpClient                                 │  │
│  │     refresher: TokenRefresher ◄──────────────────────────────┐     │  │
│  └──────────────────────────────────────────────────────────────│─────┘  │
│                                                                 │        │
│  ┌──────────────────────────────────────────────────────────────│─────┐  │
│  │ AuthenticatedHttpClient                                      │     │  │
│  │   - Wraps ObservableHttpClient                               │     │  │
│  │   - Calls _getToken() per request                            │     │  │
│  │   - Injects Authorization header if token present            │     │  │
│  │   - Does NOT retry on 401                                    │     │  │
│  │                                                              │     │  │
│  │   Dependencies:                                              │     │  │
│  │     inner: ObservableHttpClient                              │     │  │
│  │     _getToken: String? Function() ◄──────────────────────────│─┐   │  │
│  └──────────────────────────────────────────────────────────────│─│───┘  │
│                                                                 │ │      │
│  ┌──────────────────────────────────────────────────────────────│─│───┐  │
│  │ TokenRefreshService (pure Dart)                              │ │   │  │
│  │   - refresh() → TokenRefreshResult (sealed type)             │ │   │  │
│  │   - Fetches OIDC discovery, POSTs to token endpoint          │ │   │  │
│  │   - SSRF protection via origin validation                    │ │   │  │
│  │                                                              │ │   │  │
│  │   Dependencies:                                              │ │   │  │
│  │     httpClient: baseHttpClient (no auth, internal to core)   │ │   │  │
│  └──────────────────────────────────────────────────────────────│─│───┘  │
└─────────────────────────────────────────────────────────────────│─│──────┘
                                                                  │ │
                                        implements &              │ │
                                        injects                   │ │
                                                                  │ │
┌─────────────────────────────────────────────────────────────────│─│──────┐
│                           Flutter Frontend                      │ │      │
│                                                                 │ │      │
│  ┌──────────────────────────────────────────────────────────────│─│───┐  │
│  │ AuthNotifier implements TokenRefresher ──────────────────────┘ │   │  │
│  │   - Interprets AuthProviderConfig as OidcIssuer                │   │  │
│  │   - Runs flutter_appauth flow (sign in/out)                    │   │  │
│  │   - Stores tokens in flutter_secure_storage                    │   │  │
│  │   - Delegates refresh to TokenRefreshService                   │   │  │
│  │   - Implements needsRefresh, refreshIfExpiringSoon(), tryRefresh() │  │
│  └────────────────────────────────────────────────────────────────│───┘  │
│                                                                   │      │
│  api_provider.dart wiring:                                        │      │
│    _getToken: () => ref.read(accessTokenProvider) ────────────────┘      │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Migration Plan

1. **Add to `soliplex_client`:**
   - `AuthProviderConfig` model in `lib/src/auth/`
   - `AuthenticatedHttpClient` decorator in `lib/src/http/`
   - `TokenRefresher` interface in `lib/src/http/`
   - `RefreshingHttpClient` decorator in `lib/src/http/`
   - `fetchAuthProviders()` in `SoliplexApi`

2. **Keep in Flutter frontend:**
   - `OidcIssuer` (frontend interpretation of `AuthProviderConfig`)
   - All Riverpod providers/notifiers
   - `auth_flow.dart` (flutter_appauth)
   - Token storage, `AuthNotifier` implementing `TokenRefresher`

3. **Refactor Flutter wiring:**
   - Use core's `AuthenticatedHttpClient` instead of `_AuthenticatedHttpClient`
   - Frontend provides token getter closure and `TokenRefresher` implementation
   - Decorator order: `Refreshing(Authenticated(Observable(Platform)))`

## System Integration

### Full Architecture Diagram

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Flutter App                                    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         UI Layer                                     │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │   │
│  │  │ LoginScreen │  │ RoomsScreen │  │ ChatScreen  │  │ Settings   │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘  │   │
│  └─────────┼────────────────┼────────────────┼───────────────┼─────────┘   │
│            │                │                │               │             │
│            │    ref.watch(authProvider)      │               │             │
│            ▼                ▼                ▼               ▼             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Providers (Riverpod)                           │   │
│  │                                                                     │   │
│  │  ┌──────────────────┐      ┌──────────────────┐                    │   │
│  │  │   authProvider   │◄────►│  configProvider  │                    │   │
│  │  │  (AuthNotifier)  │      │ (ConfigNotifier) │                    │   │
│  │  │ impl TokenRefresher     └──────────────────┘                    │   │
│  │  └────────┬─────────┘                                              │   │
│  │           │                                                         │   │
│  │           │ credentials + TokenRefresher interface                  │   │
│  │           ▼                                                         │   │
│  │  ┌──────────────────┐      ┌──────────────────┐                    │   │
│  │  │    apiProvider   │─────►│ agUiClientProvider│                   │   │
│  │  │  (SoliplexApi)   │      │   (AG-UI Client) │                    │   │
│  │  └────────┬─────────┘      └────────┬─────────┘                    │   │
│  └───────────┼─────────────────────────┼──────────────────────────────┘   │
│              │                         │                                   │
│              ▼                         ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         HTTP Decorator Stack                         │   │
│  │                                                                     │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ RefreshingHttpClient (core - soliplex_client)                 │   │   │
│  │  │   - Proactive refresh via TokenRefresher.refreshIfExpiringSoon│  │   │
│  │  │   - 401 retry via TokenRefresher.tryRefresh (once only)      │   │   │
│  │  │   - Uses baseHttpClient for refresh (bypasses auth layer)    │   │   │
│  │  └──────────────────────────┬──────────────────────────────────┘   │   │
│  │                             │                                       │   │
│  │                             ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ AuthenticatedHttpClient (core - soliplex_client)             │   │   │
│  │  │   - Injects Authorization: Bearer {token}                    │   │   │
│  │  │   - Does NOT handle refresh or retry                         │   │   │
│  │  └──────────────────────────┬──────────────────────────────────┘   │   │
│  │                             │                                       │   │
│  │                             ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ ObservableHttpClient (core - soliplex_client)                │   │   │
│  │  │   - Notifies HttpObserver of all requests/responses          │   │   │
│  │  │   - ALL traffic (backend + IdP refresh) goes through here    │   │   │
│  │  └──────────────────────────┬──────────────────────────────────┘   │   │
│  │                             │                                       │   │
│  │                             ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ Platform HTTP Client (core - soliplex_client_native)         │   │   │
│  │  │   - CupertinoHttpClient (iOS/macOS) / DartHttpClient         │   │   │
│  │  └──────────────────────────┬──────────────────────────────────┘   │   │
│  └─────────────────────────────┼──────────────────────────────────────┘   │
│                                │                                           │
│  Token Refresh Path (bypasses AuthenticatedHttpClient):                    │
│  AuthNotifier.tryRefresh() → auth_flow.refreshTokens() → baseHttpClient   │
│                                │                                           │
└────────────────────────────────┼───────────────────────────────────────────┘
                                 │ HTTPS
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                      Soliplex Backend Infrastructure                       │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                        Soliplex API Server                          │  │
│  │  ┌───────────────────┐  ┌────────────────────────────────────────┐  │  │
│  │  │ GET /api/login    │  │ /api/v1/* (protected)                  │  │  │
│  │  │ Returns IdP info: │  │ Validates Bearer token against IdP    │  │  │
│  │  │ • server_url      │  │                                        │  │  │
│  │  │ • client_id       │  └────────────────────────────────────────┘  │  │
│  │  │ • scope           │                                              │  │
│  │  └───────────────────┘                                              │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    OIDC Identity Provider (Keycloak)                │  │
│  │  server_url: https://sso.domain.net/realms/soliplex                 │  │
│  │                                                                     │  │
│  │  ┌────────────────────────────────────────────────────────────┐    │  │
│  │  │ /.well-known/openid-configuration ◄── OIDC discovery        │    │  │
│  │  │ /protocol/openid-connect/auth     ◄── flutter_appauth login │    │  │
│  │  │ /protocol/openid-connect/token    ◄── code exchange & refresh│   │  │
│  │  └────────────────────────────────────────────────────────────┘    │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘

Auth Flow (Direct OIDC via flutter_appauth):
1. App calls GET /api/login → gets IdP config (server_url, client_id, scope)
2. flutter_appauth opens system browser → IdP login page (server_url)
3. User authenticates with IdP
4. IdP redirects to app with auth code
5. flutter_appauth exchanges code for tokens at IdP token endpoint (PKCE)
6. App stores tokens, uses for API calls
7. On refresh: auth_flow.refreshTokens() → baseHttpClient → IdP token endpoint
```

### Auth Components

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                         lib/core/auth/                                      │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  AuthState (sealed class)                                             │ │
│  │                                                                       │ │
│  │  ┌─────────────────┐    ┌──────────────────────────────────────────┐ │ │
│  │  │ Unauthenticated │    │ Authenticated                            │ │ │
│  │  │                 │    │   accessToken, refreshToken, idToken     │ │ │
│  │  │                 │    │   expiresAt, issuerId, clientId          │ │ │
│  │  │                 │    │   issuerDiscoveryUrl                      │ │ │
│  │  │                 │    │   isExpired, needsRefresh (computed)     │ │ │
│  │  └─────────────────┘    └──────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                  │                                          │
│                                  │ persisted to                             │
│                                  ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                 flutter_secure_storage (via AuthStorage)              │  │
│  │                                                                       │  │
│  │  iOS/macOS: Keychain    Android: EncryptedSharedPreferences          │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  TokenRefresher (interface) — from soliplex_client                    │  │
│  │    needsRefresh: bool                                                 │  │
│  │    refreshIfExpiringSoon() → proactive refresh                        │  │
│  │    tryRefresh() → attempt refresh, return success/failure             │  │
│  │                                                                       │  │
│  │  Note: Implementers need access to baseHttpClient (not the            │  │
│  │  RefreshingHttpClient being configured) for token refresh calls.      │  │
│  │  This dependency is injected via constructor, not interface.          │  │
│  └───────────────────────────────┬──────────────────────────────────────┘  │
│                                  │                                          │
│                                  │ implemented by                           │
│                                  ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  AuthNotifier implements TokenRefresher                               │  │
│  │                                                                       │  │
│  │  Dependencies captured in build() via providers (enables testing):    │  │
│  │    late final AuthStorage _storage                                    │  │
│  │    late final TokenRefreshService _refreshService                     │  │
│  │                                                                       │  │
│  │  signIn(issuer)      → flutter_appauth flow                           │  │
│  │  signOut()           → endSession + clears tokens from storage        │  │
│  │  tryRefresh()        → delegates to _refreshService.refresh()         │  │
│  │  restoreSession()    → loads tokens from storage on app start         │  │
│  └───────────────────────────────┬──────────────────────────────────────┘  │
│                                  │                                          │
│                                  │ delegates to                             │
│                                  ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  auth_flow.dart                                                       │  │
│  │                                                                       │  │
│  │  authenticate(issuer) → AuthResult (flutter_appauth)                  │  │
│  │  endSession(...)      → IdP logout (flutter_appauth)                  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  TokenRefreshService (pure Dart - from soliplex_client)               │  │
│  │                                                                       │  │
│  │  Constructor: TokenRefreshService(httpClient: SoliplexHttpClient)     │  │
│  │    httpClient: base client (not authenticated) for refresh calls      │  │
│  │                                                                       │  │
│  │  refresh(...) → TokenRefreshResult (sealed type)                      │  │
│  │    - TokenRefreshSuccess: new tokens                                  │  │
│  │    - TokenRefreshFailure: invalidGrant, networkError, unknownError    │  │
│  │                                                                       │  │
│  │  Handles: OIDC discovery, token refresh POST, SSRF validation         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  RefreshingHttpClient (decorator) — from soliplex_client              │  │
│  │                                                                       │  │
│  │  Constructor: RefreshingHttpClient(inner, refresher)                  │  │
│  │    inner: AuthenticatedHttpClient (for normal requests)               │  │
│  │    refresher: TokenRefresher (for refresh operations)                 │  │
│  │                                                                       │  │
│  │  Note: Does NOT receive baseHttpClient directly. The TokenRefresher   │  │
│  │  implementation (AuthNotifier) handles the baseClient access.         │  │
│  │                                                                       │  │
│  │  Behavior:                                                            │  │
│  │    - Proactive refresh via refresher.refreshIfExpiringSoon()          │  │
│  │    - 401 retry via refresher.tryRefresh() (once only, CWE-834)        │  │
│  │    - Completer pattern for concurrent refresh deduplication           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  OidcIssuer (slim model)                                              │  │
│  │                                                                       │  │
│  │  id, title, serverUrl, clientId, scope                                │  │
│  │  discoveryUrl (computed from serverUrl)                               │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘

HTTP Client Dependency Clarification:

┌─────────────────────────────────────────────────────────────────────────────┐
│  Why TokenRefresher needs baseHttpClient (not the decorated stack):         │
│                                                                             │
│  RefreshingHttpClient wraps AuthenticatedHttpClient. If refresh calls       │
│  went through AuthenticatedHttpClient, the refresh_token would be sent      │
│  with an Authorization header containing the (possibly expired) access      │
│  token - this is incorrect OAuth behavior and could cause loops.            │
│                                                                             │
│  Solution: AuthNotifier receives baseHttpClient via Riverpod ref and        │
│  passes it to auth_flow.refreshTokens(). The refresh request goes           │
│  through Observable → Platform (visible in HTTP logs) but NOT through       │
│  Authenticated (no auth header added).                                      │
│                                                                             │
│  Request paths:                                                             │
│    Normal API call: Refreshing → Authenticated → Observable → Platform     │
│    Token refresh:   auth_flow.refreshTokens() → Observable → Platform      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### HTTP Observability

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                        HTTP Request Lifecycle                               │
│                                                                             │
│   API Call (e.g., fetchRooms())                                            │
│        │                                                                    │
│        ▼                                                                    │
│   ┌────────────────────────────────────────────────────────────────────┐   │
│   │ RefreshingHttpClient                                                │   │
│   │                                                                     │   │
│   │  1. Check needsRefresh → proactive refresh if needed               │   │
│   │  2. Forward request to inner client                                 │   │
│   │  3. On 401 → tryRefresh() → retry ONCE (CWE-834)                   │   │
│   └─────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│   ┌────────────────────────────────────────────────────────────────────┐   │
│   │ AuthenticatedHttpClient                                             │   │
│   │                                                                     │   │
│   │  Inject: Authorization: Bearer {token}                              │   │
│   └─────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│   ┌────────────────────────────────────────────────────────────────────┐   │
│   │ ObservableHttpClient                                                │   │
│   │                                                                     │   │
│   │  Emits HttpRequestEvent ──────────────────────────────────────┐    │   │
│   │    • method, url                                              │    │   │
│   │    • headers (Authorization: Bearer [REDACTED])               │    │   │
│   │    • body (tokens [REDACTED])                                 │    │   │
│   └─────────────────────────────┬─────────────────────────────────┼────┘   │
│                                 │                                 │         │
│                                 ▼                                 │         │
│   ┌────────────────────────────────────────────────────────────┐  │        │
│   │ Platform HTTP Client → Network                              │  │        │
│   └─────────────────────────────┬──────────────────────────────┘  │        │
│                                 │                                  │         │
│                                 ▼                                  │         │
│   ┌────────────────────────────────────────────────────────────┐   │        │
│   │ Response flows back up through the chain                    │   │        │
│   │                                                             │   │        │
│   │  ObservableHttpClient emits HttpResponseEvent ──────────┐  │   │        │
│   │    • status, headers                                    │  │   │        │
│   │    • body (tokens [REDACTED])                           │  │   │        │
│   └─────────────────────────────────────────────────────────┼──┘   │        │
│                                                              │     │         │
│                                                              ▼     ▼         │
│   ┌────────────────────────────────────────────────────────────────────┐   │
│   │                      HttpLogNotifier                                │   │
│   │                  (implements HttpObserver)                          │   │
│   │                                                                     │   │
│   │  Sanitization rules applied before logging:                         │   │
│   │    • Authorization header → "Bearer [REDACTED]"                     │   │
│   │    • Cookie/Set-Cookie headers → "[REDACTED]"                       │   │
│   │    • Query params: token, access_token, refresh_token, id_token,    │   │
│   │      code, client_secret, state → "[REDACTED]"                      │   │
│   │    • Response body tokens → "[REDACTED]"                            │   │
│   │                                                                     │   │
│   │  State: List<HttpEvent> ──► UI (HTTP Inspector / Debug Panel)      │   │
│   └────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                        What IS Observable                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  ✓ GET /api/login (fetch IdP configuration)                                │
│  ✓ GET {idp}/.well-known/openid-configuration (OIDC discovery)             │
│  ✓ POST {idp}/token (refresh calls go through our HTTP stack)              │
│  ✓ All authenticated API calls (GET /api/v1/rooms, etc.)                   │
│  ✓ 401 retry requests (after successful refresh)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                        What is NOT Observable                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  ✗ Authorization request (ASWebAuthenticationSession sandbox)              │
│  ✗ IdP login page (user authentication)                                    │
│  ✗ Code exchange by flutter_appauth (happens inside the library)           │
│                                                                             │
│  Note: With direct OIDC, the initial code exchange is handled internally   │
│  by flutter_appauth and isn't observable. Token refresh uses our HTTP      │
│  stack via refreshTokens() in auth_flow.dart, so it IS observable.         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Login Flow Sequence

```text
User taps "Login with Keycloak"
        │
        ▼
┌───────────────────┐
│ LoginScreen       │
│ signIn("keycloak")│
└────────┬──────────┘
         │
         ▼
┌───────────────────┐     ┌─────────────────────────────────────────────────┐
│ AuthNotifier      │     │ 1. Fetch IdP config: GET /api/login              │
│                   │────►│    → { server_url, client_id, scope }            │
│ signIn(issuerId)  │     │ 2. Call flutter_appauth.authorizeAndExchangeCode │
└───────────────────┘     └────────────────────┬────────────────────────────┘
                                               │
                    ┌──────────────────────────┴───────────────────────────┐
                    │                    BROWSER SANDBOX                   │
                    │              (not observable from app)               │
                    ▼                                                      │
         ┌─────────────────────┐                                          │
         │ ASWebAuthSession    │                                          │
         │ (iOS/macOS)         │                                          │
         └──────────┬──────────┘                                          │
                    │                                                      │
                    ▼                                                      │
         ┌─────────────────────────────────────────────────────────────┐  │
         │ IdP (Keycloak) - Direct OIDC                                │  │
         │ https://sso.domain.net/realms/soliplex                      │  │
         │                                                             │  │
         │  1. /protocol/openid-connect/auth                           │  │
         │     (authorization endpoint - shows login page)             │  │
         │                                                             │  │
         │  2. User authenticates                                      │  │
         │                                                             │  │
         │  3. Redirect to app with authorization code                 │  │
         │     app://callback?code=xxx&state=yyy                       │  │
         └──────────────────────────┬──────────────────────────────────┘  │
                                    │                                      │
                    └───────────────┴──────────────────────────────────────┘
                                    │
                                    ▼
         ┌─────────────────────────────────────────────────────────────────┐
         │ flutter_appauth (automatic code exchange with PKCE)             │
         │                                                                 │
         │ POST /protocol/openid-connect/token                             │
         │   grant_type=authorization_code                                 │
         │   code=xxx                                                      │
         │   code_verifier=<PKCE verifier>                                 │
         │   redirect_uri=app://callback                                   │
         │                                                                 │
         │ Response: { access_token, refresh_token, expires_in, ... }     │
         └──────────────────────────┬──────────────────────────────────────┘
                                    │
                                    ▼
         ┌─────────────────────┐     ┌─────────────────────┐
         │ AuthNotifier        │────►│ flutter_secure_     │
         │ state = Authenticated│     │ storage             │
         └──────────┬──────────┘     └─────────────────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │ GoRouter redirect   │
         │ guard allows access │
         │ → navigate to /     │
         └─────────────────────┘
```

### Logout Flow Sequence

```text
User taps "Logout"
        │
        ▼
┌───────────────────┐
│ SettingsScreen    │
│ signOut()         │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ AuthNotifier      │
│ signOut()         │
└────────┬──────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────┐
│ Get idToken and issuerDiscoveryUrl from Authenticated state │
└────────┬───────────────────────────────────────────────────┘
         │
         ├──────────────── idToken is null? ─────────────────┐
         │                                                    │
         ▼ (idToken present)                                  ▼ (no idToken)
┌─────────────────────────────────────────────┐    ┌──────────────────────┐
│ auth_flow.endSession()                       │    │ Skip endSession      │
│                                             │    │ (can't logout at IdP │
│  appAuth.endSession(EndSessionRequest(      │    │  without idToken)    │
│    idTokenHint: idToken,                    │    └──────────┬───────────┘
│    discoveryUrl: issuerDiscoveryUrl,        │               │
│    postLogoutRedirectUrl: redirectUri,      │               │
│  ))                                         │               │
└────────┬────────────────────────────────────┘               │
         │                                                    │
         │ (Opens browser to IdP logout page)                 │
         │ (IdP clears its session)                           │
         │ (Redirects back to app)                            │
         │                                                    │
         │ (If endSession fails, continues anyway)            │
         ▼                                                    │
         ├────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ state = Unauthenticated()                   │
│ (Local tokens cleared)                      │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────┐
│ GoRouter redirect   │
│ guard navigates     │
│ → to /login         │
└─────────────────────┘
```

**Key behavior:**

- `endSession` requires `idToken` from the original login
- If `idToken` is unavailable, local logout still proceeds
- If `endSession` fails (network error, IdP error), local logout still proceeds
- User is always logged out locally regardless of IdP session state

## Backend Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/login` | GET | IdP configuration (server_url, client_id, scope) |
| `/api/v1/*` | various | Protected API endpoints (require Bearer token) |

**`/api/login` Response Format:**

```json
{
  "keycloak": {
    "id": "keycloak",
    "title": "Authenticate with Keycloak",
    "server_url": "https://sso.domain.net/realms/soliplex",
    "client_id": "soliplex-service",
    "scope": "openid email profile"
  }
}
```

Note: BFF endpoints (`/api/login/{system}`, `/api/auth/{system}`) exist but are not used
with direct OIDC approach. They're available for web platform (deferred).

## Models

### AuthState

```dart
sealed class AuthState {
  const AuthState();
}

class Unauthenticated extends AuthState {
  const Unauthenticated();
}

class AuthLoading extends AuthState {
  const AuthLoading();
}

class Authenticated extends AuthState {
  final String accessToken;
  final String refreshToken;
  final DateTime expiresAt;
  final String issuerId;            // Which IdP issued tokens (for refresh)
  final String issuerDiscoveryUrl;  // OIDC discovery URL (for endSession)
  final String clientId;            // Required for token refresh
  final String idToken;             // Required for OIDC endSession

  const Authenticated({
    required this.accessToken,
    required this.refreshToken,
    required this.expiresAt,
    required this.issuerId,
    required this.issuerDiscoveryUrl,
    required this.clientId,
    required this.idToken,
  });

  bool get isExpired => DateTime.now().isAfter(expiresAt);
  bool get needsRefresh => DateTime.now().isAfter(
    expiresAt.subtract(TokenRefreshService.refreshThreshold),
  );
}
```

**Refresh Buffer Justification (1 minute):**

The 1-minute buffer before token expiry provides:

1. **Network latency margin**: Ensures refresh completes before token expires, even with slow networks
2. **Clock drift tolerance**: Small differences between client and server clocks won't cause premature 401s
3. **Reasonable for typical token lifetimes**: Keycloak default access token lifetime is 5 minutes;
   1 minute buffer means refresh at 80% of lifetime

For shorter token lifetimes (< 2 minutes), this buffer may be too aggressive. Consider making it
configurable or percentage-based (e.g., 80% of lifetime) if supporting IdPs with very short tokens.

Note: `refreshExpiresAt` intentionally omitted. Refresh token expiry is handled by
`invalid_grant` error response from IdP, avoiding client-side clock drift issues.

### Nullable Fields and Boundaries

The auth system has several nullable fields. Each null is handled at a single boundary
to avoid spreading null checks throughout the codebase.

| Field | Type | Why Nullable | Boundary |
|-------|------|--------------|----------|
| `AuthResult.refreshToken` | `String?` | Some IdPs don't issue refresh tokens | `AuthNotifier.signIn()` - defaults to empty string |
| `AuthResult.idToken` | `String?` | Some IdPs may not return id_token | Stored as-is; checked in `endSession()` |
| `AuthResult.expiresAt` | `DateTime?` | Some IdP responses omit `expires_in` | `AuthNotifier.signIn()` - defaults to 1 hour from now |
| `AuthenticatedHttpClient._getToken()` | `String?` | Returns null when unauthenticated | `_injectAuth()` - skips header if null |
| `TokenRefreshSuccess.idToken` | `String?` | OIDC spec: refresh may not return id_token | `AuthNotifier` preserves existing idToken |

**TokenRefreshSuccess.idToken Nullability (OIDC Spec Reference):**

Per [OIDC Core 1.0 Section 12.2](https://openid.net/specs/openid-connect-core-1_0.html#RefreshTokenResponse):

> "Upon successful validation of the Refresh Token, the response body is the Token Response
> of Section 3.1.3.3 except that **it might not contain an id_token**."

Whether an IdP returns a new `id_token` on refresh depends on implementation, requested scopes,
and provider-specific policies. The `TokenRefreshSuccess.idToken` field is intentionally nullable
to accurately represent what the IdP returned. Callers must preserve the existing `id_token`:

```dart
// In AuthNotifier._handleRefreshSuccess()
final idToken = result.idToken ?? current.idToken;
```

**Design principle**: Nulls represent legitimate states (e.g., no token yet, IdP didn't
provide optional field). Each null is handled at one boundary, keeping the rest of the
code simple.

### OidcIssuer

Exactly matches `/api/login` response shape:

```dart
class OidcIssuer {
  final String id;
  final String title;
  final String serverUrl;
  final String clientId;
  final String scope;

  const OidcIssuer({
    required this.id,
    required this.title,
    required this.serverUrl,
    required this.clientId,
    required this.scope,
  });
}
```

Token endpoint for refresh is derived at runtime from OIDC discovery:
`{serverUrl}/.well-known/openid-configuration`

## Providers

| Provider | Type | Purpose |
|----------|------|---------|
| `authProvider` | NotifierProvider | Auth state + actions, implements TokenRefresher |
| `baseHttpClientProvider` | Provider | Observable HTTP client for refresh (no auth header) |

Derived providers (`accessTokenProvider`, `isAuthenticatedProvider`) added when needed.

### AuthNotifier

Implements `TokenRefresher` to provide refresh capabilities to RefreshingHttpClient.

```dart
class AuthNotifier extends Notifier<AuthState> implements TokenRefresher {
  final AuthStorage _storage;

  Future<void> signIn(OidcIssuer issuer);
  Future<void> signOut();              // Calls endSession (flutter_appauth) + clears storage

  // TokenRefresher implementation
  bool get needsRefresh;               // True if token expires within 1 minute
  Future<void> refreshIfExpiringSoon(); // Proactive refresh before API calls
  Future<bool> tryRefresh();           // Uses auth_flow.refreshTokens() with baseHttpClient
}
```

Token refresh uses `ref.read(baseHttpClientProvider)` to get an observable HTTP client
that bypasses the auth layer (avoiding circular dependency).

**signOut behavior:**

- On platforms with flutter_appauth (iOS/macOS): calls `appAuth.endSession()` to end
  the IdP session, then clears local tokens
- On platforms without flutter_appauth (future): clears local tokens only; proper
  endSession support deferred until platform-specific auth is implemented

## Platform Auth Flow

Single file `auth_flow.dart` with platform-appropriate implementation:

### MVP: iOS/macOS (Direct OIDC via flutter_appauth)

Uses `flutter_appauth` with ASWebAuthenticationSession. PKCE handled automatically.

```dart
const _redirectUri = 'ai.soliplex.client://callback';

Future<AuthResult> authenticate(OidcIssuer issuer) async {
  // flutter_appauth handles:
  // - PKCE code_verifier/code_challenge generation
  // - State parameter generation and validation
  // - Opening ASWebAuthenticationSession
  // - Code exchange with IdP token endpoint

  final result = await appAuth.authorizeAndExchangeCode(
    AuthorizationTokenRequest(
      issuer.clientId,
      _redirectUri,
      discoveryUrl: issuer.discoveryUrl,
      scopes: issuer.scope.split(' '),
      externalUserAgent: ExternalUserAgent.ephemeralAsWebAuthenticationSession,
    ),
  );

  return AuthResult(
    accessToken: result.accessToken!,
    refreshToken: result.refreshToken,
    idToken: result.idToken,
    expiresAt: result.accessTokenExpirationDateTime,
  );
}
```

**Platform configuration required:**

- macOS: `Info.plist` with `CFBundleURLSchemes` for custom URL scheme
- iOS: Same `Info.plist` configuration

### Post-MVP: Desktop (Windows, Linux)

Loopback server with state validation (deferred).

### Post-MVP: Web

Redirect flow with memory-only storage (deferred).

## HTTP Integration

### Token Injection

```dart
final authenticatedTransportProvider = Provider<HttpTransport>((ref) {
  final transport = ref.watch(httpTransportProvider);
  final authState = ref.watch(authProvider);
  final token = authState is Authenticated ? authState.accessToken : null;

  return AuthenticatedHttpTransport(
    transport: transport,
    getToken: () => token,
  );
});
```

### 401 Handling

On `AuthException` (401/403):

1. If refresh token available and not expired: attempt refresh
2. If refresh fails or no refresh token: transition to Unauthenticated
3. Router redirect guard navigates to `/login`

### HTTP Observer Filtering

Filter sensitive data from logs:

```dart
const _sensitiveHeaders = {
  'authorization',
  'cookie',
  'set-cookie',
  'www-authenticate',
};

const _sensitiveParams = {
  'token',
  'access_token',
  'refresh_token',
  'id_token',
  'code',
  'client_secret',
  'state',
  'code_verifier',   // PKCE verifier
  'session_state',   // Keycloak session metadata
};

const _sensitiveBodyFields = {
  'access_token',
  'refresh_token',
  'id_token',
  'code',
  'session_state',
};
```

**Deferred (post-MVP):**

- JWT pattern regex detection (`eyJ[A-Za-z0-9-_]+\.eyJ...`) for catch-all redaction
- Response header `www-authenticate` parsing for token format leakage

## Router Integration

### Routes

| Route | Screen | Auth Required |
|-------|--------|---------------|
| `/login` | LoginScreen | No |
| `/` | HomeScreen | Yes |
| `/rooms/*` | Room screens | Yes |
| `/settings` | SettingsScreen | Yes |

### Redirect Guard

The router uses `refreshListenable` to trigger redirect re-evaluation on auth status
changes without recreating the router itself. This preserves navigation state during
token refresh (which updates auth state but shouldn't cause navigation).

```dart
final routerProvider = Provider<GoRouter>((ref) {
  // authStatusListenableProvider only fires on login/logout transitions,
  // NOT on token refresh. This prevents navigation state loss.
  final authStatusListenable = ref.watch(authStatusListenableProvider);

  return GoRouter(
    initialLocation: '/',
    refreshListenable: authStatusListenable,
    redirect: (context, state) {
      // Use ref.read() for fresh auth state, not a captured variable
      final authState = ref.read(authProvider);
      final isAuthenticated = authState is Authenticated;
      final isLoginRoute = state.matchedLocation == '/login';

      if (!isAuthenticated && !isLoginRoute) {
        return '/login';
      }
      if (isAuthenticated && isLoginRoute) {
        return '/';
      }
      return null;
    },
    // ...routes
  );
});
```

**Key implementation detail:** `_AuthStatusListenable` tracks whether user is
authenticated (boolean), not the full auth state. When tokens refresh, the boolean
stays `true`, so no notification fires and the router doesn't rebuild. On logout,
the boolean changes from `true` to `false`, triggering redirect evaluation.

### Startup UX

On app launch, `restoreSession()` checks for stored tokens. During this async check:

1. Show loading indicator (centered spinner or splash)
2. Once auth state resolves:
   - Authenticated → navigate to home
   - Unauthenticated → navigate to login

```dart
// In app initialization
await ref.read(authProvider.notifier).restoreSession();
// Auth state now resolved, router redirect guard takes over
```

## Secure Storage

| Platform | Storage Mechanism |
|----------|-------------------|
| iOS | Keychain |
| macOS | Keychain |
| Android | EncryptedSharedPreferences (post-MVP) |
| Windows | DPAPI (post-MVP) |
| Linux | libsecret (post-MVP) |
| Web | Memory only (post-MVP) |

**Keychain Configuration** (MVP):

```dart
const storage = FlutterSecureStorage(
  iOptions: IOSOptions(
    accessibility: KeychainAccessibility.first_unlock_this_device,
  ),
  mOptions: MacOsOptions(
    accessibility: KeychainAccessibility.first_unlock_this_device,
  ),
);
```

**Accessibility choice**: `first_unlock_this_device` (not `whenUnlockedThisDeviceOnly`) because:

- Enables background token refresh without requiring device to be actively unlocked
- Still prevents backup/restore to different devices (`thisDeviceOnly` suffix)
- Still requires at least one unlock after boot before tokens are accessible
- Tradeoff: tokens accessible when device is locked (after first unlock)

This prevents:

- Tokens being restored from backup to another device
- Access before first device unlock after boot

**Storage Keys**:

- `auth_access_token`
- `auth_refresh_token`
- `auth_id_token` (required for endSession)
- `auth_expires_at`
- `auth_issuer_id` (to know which IdP config to use for refresh)
- `auth_issuer_discovery_url` (required for endSession)

## Token Refresh Strategy

Backend does not provide a refresh endpoint. Client refreshes directly with IdP
using the same HTTP stack (so refresh calls are observable).

### Flow

```text
1. On app start, GET /api/login → OidcIssuer { server_url, client_id }
2. GET {server_url}/.well-known/openid-configuration → { token_endpoint }
3. Cache token_endpoint for refresh calls
4. When access_token nearing expiry (1 min before):
   POST {token_endpoint}  ◄── Goes through ObservableHttpClient
   Content-Type: application/x-www-form-urlencoded

   grant_type=refresh_token
   refresh_token={stored_refresh_token}
   client_id={client_id}

5. IdP returns: { access_token, refresh_token, expires_in, refresh_expires_in }
6. Store new tokens, update expiry times
```

### Error Handling

| Error | Action |
|-------|--------|
| `invalid_grant` | Refresh token expired/revoked → clear tokens, require re-login |
| Network error | Retry with exponential backoff, max 3 attempts |
| Other OAuth error | Log error, require re-login |

### Token Refresh Failure Handling Policy

Token refresh failures are handled differently at **startup** vs **runtime**. This
asymmetry is intentional.

#### Startup (Session Restore)

When the app launches with stored but expired tokens, `_tryRefreshStoredTokens` attempts
refresh. **All failures result in logout:**

| Failure Reason | Action |
|----------------|--------|
| `invalidGrant` | Clear tokens, logout |
| `networkError` | Clear tokens, logout |
| `noRefreshToken` | Clear tokens, logout |
| Exception thrown | Clear tokens, logout |

**Rationale:** At startup, we're trying to *establish* trust from stored credentials.
If we can't validate tokens (for any reason), we have nothing useful—the tokens are
stale and we can't verify them. Failing fast with "please log in" is clearer than
pretending authentication succeeded when we can't verify it.

#### Runtime (Active Session)

When refresh is triggered during an active session (proactive refresh or 401 retry),
`tryRefresh` distinguishes between failure types:

| Failure Reason | Action |
|----------------|--------|
| `invalidGrant` | Clear tokens, logout (refresh token is dead) |
| `networkError` | Preserve session, return `false` (transient failure) |
| `noRefreshToken` | Preserve session, return `false` (can't recover) |
| `unknownError` | Preserve session, return `false` (optimistic) |

**Rationale:** At runtime, we already established trust. A transient network error
shouldn't destroy a valid session. The user stays "authenticated" in local state and
can retry when network returns. Only a definitive rejection from the IdP (`invalidGrant`)
triggers logout.

#### Why Not Align Both to the Same Policy?

**Option: Make startup lenient (like runtime)**

If the device is offline at launch with valid refresh tokens, the user would stay
"authenticated" but unable to make API calls. This creates confusing UX: "I'm logged
in but nothing works." Every API call would fail, attempt refresh, fail again.

**Option: Make runtime strict (like startup)**

Network blips would log users out, destroying valid sessions unnecessarily. Users
would need to re-authenticate after every transient network failure.

**Chosen: Asymmetric policy**

- Startup: Strict (fail fast, clear "please log in" prompt)
- Runtime: Lenient (preserve session through transient failures)

This matches user expectations: "If I was logged in, a bad wifi moment shouldn't
kick me out. But if I'm starting fresh, just show me the login screen."

## Deployment Requirements

These are backend/infrastructure requirements outside the app's control:

| Requirement | Owner | Notes |
|-------------|-------|-------|
| Keycloak redirect URI | Backend | Must configure `net.soliplex.app://callback` in Keycloak client |
| Refresh token rotation | Backend | Keycloak should rotate refresh tokens on each use |
| CORS (web only) | Backend | Not needed for MVP (native only) |

**Refresh Token Rotation:**

If Keycloak returns a new refresh token on refresh, the app stores the new token.
If Keycloak is NOT configured for rotation, a leaked refresh token grants indefinite
access until it expires.

## Security Requirements

| Requirement | Implementation |
|-------------|----------------|
| PKCE | flutter_appauth handles automatically |
| No embedded WebView | flutter_appauth uses ASWebAuthenticationSession |
| Secure token storage | flutter_secure_storage (Keychain) with `first_unlock_this_device` |
| Token filtering in logs | HttpObserver sanitization |
| State parameter | flutter_appauth handles automatically |
| HTTPS only | Enforced by config validation |

## Implementation Slices (Vertical)

### Spike: Validate Direct OIDC on macOS + iOS

Research findings:

- [x] `/api/login` returns IdP config: `{ server_url, client_id, scope }`
- [x] Direct OIDC approach confirmed (per `clean_soliplex` implementation)
- [x] flutter_appauth supports macOS + iOS via ASWebAuthenticationSession

Spike deliverable (before Slice 1):

- [ ] Minimal test app with flutter_appauth
- [ ] Confirm login flow works with Keycloak IdP on macOS
- [ ] Confirm login flow works on iOS
- [ ] Validate token returned and usable for API call

### Slice 1: Walking Skeleton + HTTP Filtering

**Delivers**: Login on macOS, make authenticated API call, sensitive data redacted.

**Acceptance**: User can login, see protected content. HTTP inspector shows `[REDACTED]`
for tokens.

Files:

- `lib/core/auth/auth_state.dart`
- `lib/core/auth/oidc_issuer.dart`
- `lib/core/auth/auth_flow.dart`
- `lib/core/auth/auth_notifier.dart`
- `lib/core/auth/idp_client.dart`
- `lib/core/providers/auth_provider.dart`
- `lib/features/login/login_screen.dart`
- `lib/core/router/app_router.dart` (modify)
- `packages/soliplex_client/lib/src/http/http_observer.dart` (modify - filtering)
- `macos/Runner/Info.plist` (URL scheme)
- `macos/Runner/DebugProfile.entitlements`
- `macos/Runner/Release.entitlements`
- `ios/Runner/Info.plist` (URL scheme)

### Slice 2: Session Persistence

**Delivers**: Tokens survive app restart. Loading indicator during restore.

**Acceptance**: Close app while authenticated, reopen, see loading indicator briefly,
then authenticated content.

Files:

- Modify `auth_notifier.dart` to use flutter_secure_storage with Keychain config
- Add loading state handling in router/UI

### Slice 3: Token Refresh + 401 Recovery

**Delivers**: Access tokens refresh before expiry. Automatic retry on 401.

**Acceptance**: App remains authenticated beyond initial token lifetime. Expired token
triggers refresh and retry transparently.

Files:

- `lib/core/auth/authenticated_transport.dart`
- Modify `lib/core/providers/api_provider.dart`
- Modify `auth_notifier.dart` for refresh logic via IdpClient

## Dependencies

```yaml
dependencies:
  flutter_appauth: ^8.0.0        # Native OAuth (iOS/macOS)
  flutter_secure_storage: ^9.2.0 # Secure token storage
```

Post-MVP:

```yaml
  url_launcher: ^6.3.0           # System browser (desktop)
```

## Test Plan

### Unit Tests

- [x] AuthState.isExpired / needsRefresh
- [x] TokenRefreshService (13 tests: success, validation, errors, SSRF)
- [x] RefreshingHttpClient (19 tests: retry, deduplication, proactive refresh)
- [x] AuthNotifier (15 tests: restore, runtime refresh, failure policies)
- [ ] Token parsing from callback URI
- [ ] State parameter generation and validation
- [x] HTTP observer filtering rules

### Widget Tests

- [ ] LoginScreen fetches and renders providers
- [ ] LoginScreen handles loading/error states
- [ ] Auth redirect guard behavior

### Integration Tests

- [x] Full auth flow on macOS (spike validated)
- [x] Full auth flow on iOS (spike validated)
- [ ] Token refresh with artificially short expiry (manual test)
- [x] Session restore: write tokens, restart provider, verify state (unit tested)

## File Structure

```text
lib/core/auth/
├── auth_state.dart              # Sealed class (AuthState, Authenticated, etc.)
├── auth_storage.dart            # Keychain storage wrapper
├── auth_notifier.dart           # State management + TokenRefresher impl
├── auth_provider.dart           # Riverpod providers
├── auth_flow.dart               # authenticate, endSession (flutter_appauth)
└── oidc_issuer.dart             # Model from /api/login

packages/soliplex_client/lib/src/http/
├── token_refresher.dart         # Interface for refresh operations
└── refreshing_http_client.dart  # HTTP decorator for refresh + 401 retry

packages/soliplex_client/lib/src/auth/
└── token_refresh_service.dart   # Pure Dart service for token refresh

packages/soliplex_client/lib/src/api/
└── fetch_auth_providers.dart    # Backend API for /api/login

packages/soliplex_client/lib/src/domain/
└── auth_provider_config.dart    # Domain model for auth providers

lib/core/providers/
└── api_provider.dart            # HTTP client wiring with RefreshingHttpClient

lib/features/login/
└── login_screen.dart            # Provider selection UI

Platform config:
├── macos/Runner/Info.plist      # URL scheme
├── macos/Runner/*.entitlements  # Network access
└── ios/Runner/Info.plist        # URL scheme
```

## Component Summary

| Component | Purpose | Lines (est) |
|-----------|---------|-------------|
| AuthState | Sealed class with token fields | ~60 |
| AuthStorage | Keychain storage wrapper | ~80 |
| AuthNotifier | State management + TokenRefresher impl | ~250 |
| auth_flow.dart | authenticate + endSession (flutter_appauth) | ~80 |
| OidcIssuer | Model from /api/login | ~50 |
| TokenRefresher | Interface for refresh operations | ~20 |
| TokenRefreshService | Pure Dart refresh logic with result type | ~230 |
| RefreshingHttpClient | HTTP decorator, 401 retry, CWE-834 | ~120 |
| **Total** | | **~890** |

## Resolved Questions

1. **Auth approach**: Direct OIDC via flutter_appauth (not BFF pattern)
2. **Token refresh**: Via IdpClient using shared HTTP client (observable)
3. **HTTP client architecture**: Single HTTP client, ObservableHttpClient wraps it, both SoliplexApi and IdpClient use it
4. **Logout**: Full OIDC logout via `endSession` on platforms with flutter_appauth (iOS/macOS); local-only logout on other platforms until proper auth is implemented
5. **Multiple providers**: Support one at a time (can switch by logging out first)
6. **Auth observability**: Browser flow not observable; refresh calls are observable
7. **Platform scope**: MVP = macOS + iOS; Desktop/Web deferred
8. **Keychain security**: `first_unlock_this_device` to enable background refresh while preventing backup/restore attacks
9. **Startup UX**: Loading indicator until auth state resolves
10. **refreshExpiresAt**: Omitted - let `invalid_grant` signal refresh token expiry

## Web Platform Support (Deferred)

Web requires a different authentication approach because:

1. `flutter_appauth` uses `dart:ffi` which is unavailable on web
2. `cupertino_http` (used by `soliplex_client_native`) also uses `dart:ffi`
3. CORS restrictions prevent direct OIDC token exchange from browser

### Backend-For-Frontend (BFF) Pattern

The backend already provides BFF endpoints for web authentication:

- `GET /api/login/{provider_id}?return_to={callback_url}` - Initiates OAuth flow
- Backend handles PKCE, code exchange, and redirects back with tokens

### Implementation Requirements

**HTTP Client for Web:**

`soliplex_client_native` unconditionally exports `cupertino_http_client.dart`, which imports
`cupertino_http` (dart:ffi). Fix with conditional export:

```dart
// clients.dart
export 'cupertino_http_client.dart'
    if (dart.library.js_interop) 'cupertino_http_client_web.dart';
```

Create `cupertino_http_client_web.dart` that throws `UnsupportedError` if instantiated
(web should use `DartHttpClient` via `createPlatformClient()` instead).

**Auth Flow for Web:**

New files needed (reference: `clean_soliplex/src/flutter/lib/core/auth/`):

| File | Purpose |
|------|---------|
| `callback_params.dart` | Sealed class for URL callback params |
| `web_auth_callback_handler.dart` | Conditional import dispatcher |
| `web_auth_callback_native.dart` | No-op for native platforms |
| `web_auth_callback_web.dart` | Extracts tokens from URL using `web` package |
| `web_auth_pending_storage.dart` | Stores pending auth session for callback |
| `features/auth/auth_callback_screen.dart` | Route `/auth/callback` |

**Auth Flow Changes:**

Modify `auth_flow.dart` to detect web platform and redirect to backend BFF endpoint
instead of using `flutter_appauth`. Web flow:

1. User clicks login → redirect to `/api/login/{provider_id}?return_to=/auth/callback`
2. Backend handles OAuth, redirects back with `?token=xxx&refresh_token=xxx&expires_in=xxx`
3. `AuthCallbackScreen` extracts tokens from URL, stores them, navigates to home

**Router Changes:**

Add `/auth/callback` route that renders `AuthCallbackScreen`.

**Dependencies:**

```yaml
dependencies:
  url_launcher: ^6.3.0  # For web redirect
  web: ^1.0.0           # For URL manipulation on web
```

**Token Storage:**

Web should use memory-only storage (no `flutter_secure_storage` persistence) due to
browser security model. Tokens cleared on page refresh.

### Estimated Effort

~6-8 new files, modifications to auth_flow.dart, router, and soliplex_client_native.
Approximately 400-600 lines of new code.

## Deferred Items

- Windows/Linux loopback server implementation (includes endSession support)
- Web platform authentication (see "Web Platform Support" section above)
- Multiple simultaneous provider sessions
- Android support (flutter_appauth supported, endSession will work)
- JWT pattern regex for catch-all token redaction in logs
- `www-authenticate` header parsing
- Auth-optional mode: skip login when backend returns empty providers list
- AuthNotifier testability: inject AuthFlow interface for unit testing
- OIDC nonce parameter: verify flutter_appauth handles internally or add explicit nonce

---

## Implementation Progress

Track implementation status here. Update after each phase.

### Spike Status: ✅ Complete

- [x] Add flutter_appauth dependency (v11.0.0)
- [x] Configure macOS URL scheme (`ai.soliplex.client://callback`)
- [x] Create spike test screen at `/auth-spike`
- [x] macOS app builds and runs successfully
- [x] Configure iOS URL scheme (`ai.soliplex.client://callback`)
- [x] Test login flow on macOS
- [x] Test login flow on iOS (simulator)
- [x] Validate token usable for API call

**Spike Findings:**

- flutter_appauth v11.0 API: use `externalUserAgent: ExternalUserAgent.ephemeralAsWebAuthenticationSession`
- Redirect URI must match Keycloak client config: `ai.soliplex.client://callback`
- OIDC discovery and token exchange work correctly with pydio Keycloak
- Access token successfully used for authenticated API calls
- Tested on both macOS and iOS (simulator) - both platforms work

**Files created:**

- `lib/core/auth/oidc_issuer.dart` - OidcIssuer model
- `lib/core/auth/auth_flow.dart` - flutter_appauth wrapper
- `lib/features/auth_spike/auth_spike_screen.dart` - test screen

### Slice 1 Status: ✅ Complete

- [x] `lib/core/auth/auth_state.dart` - Sealed AuthState classes
- [x] `lib/core/auth/oidc_issuer.dart` - OidcIssuer wrapper
- [x] `lib/core/auth/auth_flow.dart` - flutter_appauth wrapper with generic error messages
- [x] `lib/core/auth/auth_notifier.dart` - Riverpod state management
- [x] `lib/core/auth/auth_provider.dart` - Auth providers (authProvider, oidcIssuersProvider)
- [x] `lib/features/login/login_screen.dart` - Login UI with provider selection
- [x] `lib/core/router/app_router.dart` - Auth-aware routing with redirect
- [x] `lib/core/providers/http_log_provider.dart` - Sensitive query param redaction
- [x] `lib/core/providers/api_provider.dart` - Authenticated HTTP client wiring
- [x] `packages/soliplex_client/.../authenticated_http_client.dart` - Token injection
- [x] `packages/soliplex_client/.../fetch_auth_providers.dart` - Backend API
- [x] `packages/soliplex_client/.../auth_provider_config.dart` - Domain model
- [ ] `lib/core/auth/idp_client.dart` - Deferred (YAGNI for now)

**Notes:**

- `idp_client.dart` deferred - direct API calls sufficient for MVP
- HTTP filtering in `http_log_provider.dart` not `http_observer.dart`
- Error messages sanitized per Sentinel review (generic to user, full in logs)

### Slice 2 Status: ✅ Complete

- [x] `lib/core/auth/auth_storage.dart` - Secure storage wrapper with Keychain config
- [x] `lib/core/auth/auth_notifier.dart` - Session restore and token persistence
- [x] `lib/core/auth/auth_state.dart` - Safe `toString()` on all states (no token exposure)
- [x] `lib/app.dart` - Loading screen during auth restore
- [x] `lib/main.dart` - `clearOnReinstall()` for iOS keychain persistence
- [x] `lib/features/settings/settings_screen.dart` - Sign out button (triggers endSession + clears storage)
- [x] `test/core/auth/auth_storage_test.dart` - Storage unit tests

**Notes:**

- Keychain uses `first_unlock_this_device` (not spec's original `whenUnlockedThisDeviceOnly`)
  to enable background token refresh. Spec updated to reflect this.
- `clearOnReinstall()` handles iOS behavior where Keychain persists across app reinstalls
- Sign out uses `flutter_appauth.endSession()` to properly terminate IdP session

### Slice 3 Status: ✅ Complete

- [x] `lib/core/auth/auth_storage.dart` - Add clientId to storage
- [x] `lib/core/auth/auth_state.dart` - Add clientId to Authenticated, require idToken
- [x] `lib/core/auth/auth_notifier.dart` - Store clientId, implement TokenRefresher
- [x] `lib/core/auth/auth_flow.dart` - Simplified to just authenticate/endSession
- [x] `packages/soliplex_client/.../token_refresher.dart` - Interface for refresh operations
- [x] `packages/soliplex_client/.../refreshing_http_client.dart` - HTTP decorator with 401 retry
- [x] `packages/soliplex_client/.../token_refresh_service.dart` - Pure Dart refresh logic
- [x] `lib/core/auth/auth_provider.dart` - Add tokenRefreshServiceProvider
- [x] `lib/core/providers/api_provider.dart` - Wire RefreshingHttpClient
- [x] Handle expired tokens on session restore (attempt refresh before clearing)
- [x] Unit tests for TokenRefreshService (13 tests)
- [x] Unit tests for RefreshingHttpClient (19 tests)
- [x] Unit tests for AuthNotifier (15 tests)

**Implementation Notes:**

- Token refresh extracted to `TokenRefreshService` (pure Dart, in soliplex_client)
- Returns sealed `TokenRefreshResult` type (Success/Failure) instead of exceptions
- SSRF protection: validates token endpoint origin matches discovery URL
- `RefreshingHttpClient` decorator pattern per blacksmith/sentinel review
- Single retry limit prevents infinite 401→refresh→401 loops (CWE-834)
- Completer pattern deduplicates concurrent refresh attempts with microtask cleanup
- `TokenRefresher` interface decouples HTTP client from AuthNotifier
- `idToken` now required (not nullable) - needed for proper OIDC logout
- `clientId` stored in Keychain alongside other tokens for refresh

**Architectural Decision (2026-01-05):**

Per blacksmith consultation, AuthNotifier implementing TokenRefresher is valid DIP:

- RefreshingHttpClient depends only on TokenRefresher abstraction
- AuthNotifier provides implementation
- No actual inversion - the interface is in the right place (HTTP layer defines needs)

Testability improved by:

- Extracting refresh HTTP logic to `TokenRefreshService` (pure Dart, constructor injection)
- AuthNotifier captures dependencies in `build()` via `late final` fields
- Test by overriding providers (`authStorageProvider`, `tokenRefreshServiceProvider`)

**Riverpod Notifier Dependency Injection Pattern:**

Riverpod's `Notifier` class doesn't support constructor injection because `NotifierProvider`
uses `AuthNotifier.new` (the default constructor). The `ref` object is only available
inside `build()` and instance methods, not in the constructor.

The solution is `late final` fields initialized at the start of `build()`:

```dart
class AuthNotifier extends Notifier<AuthState> implements TokenRefresher {
  late final AuthStorage _storage;
  late final TokenRefreshService _refreshService;

  @override
  AuthState build() {
    _storage = ref.read(authStorageProvider);
    _refreshService = ref.read(tokenRefreshServiceProvider);
    // ...
  }
}
```

**Lifecycle guarantee:** Riverpod calls `build()` before exposing the Notifier to callers.
No instance method can be invoked until `build()` completes and returns the initial state.
The `late final` fields are always initialized before any method accesses them.

### Router Navigation Preservation Fix (2026-01-06)

Fixed issue where token refresh caused navigation state loss. The router was using
`ref.watch(authProvider)` which recreated the GoRouter on every auth state change
(including token refresh), resetting navigation to `initialLocation: '/'`.

**Solution:**

- Added `authStatusListenableProvider` that only fires on login/logout transitions
- Router uses `refreshListenable` pattern instead of `ref.watch(authProvider)`
- Redirect callback uses `ref.read(authProvider)` for fresh state reads

**Files modified:**

- `lib/core/auth/auth_provider.dart` - Added `_AuthStatusListenable`
- `lib/core/router/app_router.dart` - Updated to use `refreshListenable`
- `test/core/router/app_router_test.dart` - Added tests for auth state changes

**Tests added:**

- `logout from deep navigation redirects to /login`
- `token refresh preserves navigation location`

### Remaining Work

**Tests (incremental coverage, not blocking):**

| Category | Item | Priority |
|----------|------|----------|
| Unit | Token parsing from callback URI | Low |
| Unit | State parameter generation/validation | Low |
| Widget | LoginScreen fetches/renders providers | Medium |
| Widget | LoginScreen loading/error states | Medium |
| Widget | Auth redirect guard behavior | Medium |
| Manual | Token refresh with artificially short expiry | Medium |

**Current test coverage:** 47 unit tests across TokenRefreshService (13), RefreshingHttpClient (19),
and AuthNotifier (15). Core token refresh functionality is well-tested.

**Not remaining (deferred to post-MVP):** See "Deferred Items" section above for Windows/Linux,
Web platform, Android, and other post-MVP work.
