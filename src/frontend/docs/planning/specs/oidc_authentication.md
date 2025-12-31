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

**Wrapping hierarchy:** `Authenticated(Observable(Platform))`

```dart
// 1. Platform client (innermost)
final platform = createPlatformClient();

// 2. Observable wraps Platform
final observable = ObservableHttpClient(client: platform, observers: [...]);

// 3. Authenticated wraps Observable (outermost)
final authenticated = AuthenticatedHttpClient(client: observable, getToken: ...);
```

**Call order for requests:**

```text
Caller
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
Authenticated receives response (throws on 401)
  ↓
Caller
```

**Why this order:**

- Observer sees requests WITH auth headers (accurate logging)
- Observer sees all responses including 401s before Authenticated processes them
- Debugging auth issues shows actual headers sent

### 401 Retry Architecture

**Key decision:** `AuthenticatedHttpClient` does NOT retry. It only adds tokens.

Retry logic lives in the application layer (AuthNotifier) so ALL HTTP traffic is
observable:

```text
1. Original request → Authenticated → Observable → Platform
2. 401 response     ← (observer sees this)
3. AuthNotifier catches 401, triggers refresh
4. Refresh request  → Authenticated → Observable → Platform
5. Refresh response ← (observer sees this)
6. AuthNotifier retries original request
7. Retry request    → Authenticated → Observable → Platform
8. Final response   ← (observer sees this)
```

**Observer sees all 4+ HTTP calls.** No visibility is lost.

```dart
// In AuthNotifier - orchestration layer
Future<T> executeWithAuth<T>(Future<T> Function() request) async {
  try {
    return await request();
  } on AuthException catch (e) {
    if (e.statusCode == 401) {
      await refresh();  // Goes through same observable stack
      return await request();  // Retry goes through same stack
    }
    rethrow;
  }
}
```

### Flow Diagram

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           soliplex_client (core)                            │
│                                                                             │
│  fetchAuthProviders() ──► List<AuthProviderConfig>                          │
│                                 │                                           │
│                                 │ Core doesn't interpret this               │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ AuthenticatedHttpClient                                              │   │
│  │   - Wraps ObservableHttpClient (which wraps Platform)                │   │
│  │   - Calls _getToken() per request                                    │   │
│  │   - Injects Authorization header if token present                    │   │
│  │   - Does NOT retry on 401                                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                   ▲                                                         │
│                   │ _getToken: String? Function()                           │
└───────────────────┼─────────────────────────────────────────────────────────┘
                    │
┌───────────────────┼─────────────────────────────────────────────────────────┐
│                   │               Flutter Frontend                          │
│                   │                                                         │
│  ┌────────────────┴────────────────────────────────────────────────────┐   │
│  │ Token Getter (provided to core)                                      │   │
│  │   () => ref.read(accessTokenProvider)                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                   ▲                                                         │
│                   │                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ AuthNotifier                                                         │   │
│  │   - Interprets AuthProviderConfig as OidcIssuer                      │   │
│  │   - Runs flutter_appauth flow                                        │   │
│  │   - Stores tokens in flutter_secure_storage                          │   │
│  │   - Orchestrates refresh and 401 retry                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Migration Plan

1. **Add to `soliplex_client`:**
   - `AuthProviderConfig` model in `lib/src/auth/`
   - `AuthenticatedHttpClient` decorator in `lib/src/http/`
   - `fetchAuthProviders()` in `SoliplexApi`

2. **Keep in Flutter frontend:**
   - `OidcIssuer` (frontend interpretation of `AuthProviderConfig`)
   - All Riverpod providers/notifiers
   - `auth_flow.dart` (flutter_appauth)
   - Token storage, refresh orchestration, 401 retry logic

3. **Refactor Flutter wiring:**
   - Use core's `AuthenticatedHttpClient` instead of `_AuthenticatedHttpClient`
   - Frontend provides token getter closure
   - Decorator order: `Authenticated(Observable(Platform))`

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
│  │  └────────┬─────────┘      └──────────────────┘                    │   │
│  │           │                                                         │   │
│  │           │ credentials                                             │   │
│  │           ▼                                                         │   │
│  │  ┌──────────────────┐      ┌──────────────────┐                    │   │
│  │  │    apiProvider   │─────►│ agUiClientProvider│                   │   │
│  │  │  (SoliplexApi)   │      │   (AG-UI Client) │                    │   │
│  │  └────────┬─────────┘      └────────┬─────────┘                    │   │
│  └───────────┼─────────────────────────┼──────────────────────────────┘   │
│              │                         │                                   │
│              ▼                         ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    HTTP Layer (soliplex_client)                     │   │
│  │                                                                     │   │
│  │  ┌────────────────────────┐      ┌────────────────────────┐        │   │
│  │  │      SoliplexApi       │      │       IdpClient        │        │   │
│  │  │   (backend calls)      │      │   (token refresh)      │        │   │
│  │  │   + auth headers       │      │   to IdP endpoint      │        │   │
│  │  └───────────┬────────────┘      └───────────┬────────────┘        │   │
│  │              │                               │                      │   │
│  │              └───────────────┬───────────────┘                      │   │
│  │                              │                                      │   │
│  │                              ▼                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │              ObservableHttpClient                            │   │   │
│  │  │  Wraps single HTTP client, notifies HttpObserver             │   │   │
│  │  │  ALL traffic (backend + IdP) goes through here               │   │   │
│  │  └──────────────────────────┬──────────────────────────────────┘   │   │
│  │                             │                                       │   │
│  │                             ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │              Platform HTTP Client (single instance)          │   │   │
│  │  │  (CupertinoHttpClient / DartHttpClient)                      │   │   │
│  │  └──────────────────────────┬──────────────────────────────────┘   │   │
│  └─────────────────────────────┼──────────────────────────────────────┘   │
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
│  │  │ /.well-known/openid-configuration                           │    │  │
│  │  │ /protocol/openid-connect/auth  ◄── flutter_appauth login    │    │  │
│  │  │ /protocol/openid-connect/token ◄── code exchange & refresh  │    │  │
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
```

### Auth Components

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                         lib/core/auth/ [NEW]                                │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  AuthState (sealed class)                                             │ │
│  │                                                                       │ │
│  │  ┌─────────────────┐    ┌──────────────────────────────────────────┐ │ │
│  │  │ Unauthenticated │    │ Authenticated                            │ │ │
│  │  │                 │    │   accessToken, refreshToken              │ │ │
│  │  │                 │    │   expiresAt, refreshExpiresAt            │ │ │
│  │  │                 │    │   userInfo?                              │ │ │
│  │  │                 │    │   isExpired, needsRefresh (computed)     │ │ │
│  │  └─────────────────┘    └──────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                  │                                          │
│                                  │ persisted to                             │
│                                  ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                 flutter_secure_storage (direct)                       │  │
│  │                                                                       │  │
│  │  iOS/macOS: Keychain    Android: EncryptedSharedPreferences          │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      AuthNotifier                                     │  │
│  │  signIn(issuerId)    → delegates to platform auth flow                │  │
│  │  signOut()           → endSession + clears tokens from storage        │  │
│  │  refresh()           → calls IdP token endpoint (via HTTP stack)      │  │
│  │  restoreSession()    → loads tokens from storage on app start         │  │
│  └───────────────────────────────┬──────────────────────────────────────┘  │
│                                  │                                          │
│                                  │ delegates to                             │
│                                  ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                   auth_flow.dart (single file)                        │  │
│  │                                                                       │  │
│  │  authenticate(provider, backendUrl) → tokens                          │  │
│  │                                                                       │  │
│  │  MVP: flutter_appauth for iOS/macOS                                   │  │
│  │  Post-MVP: Add desktop loopback, web redirect                         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      OidcIssuer (slim model)                          │  │
│  │                                                                       │  │
│  │  id, title  (from /api/login)                                         │  │
│  │  serverUrl, clientId, tokenEndpoint  (added when needed for refresh)  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
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
│   │ AuthenticatedHttpTransport                                  │  │        │
│   │                                                             │  │        │
│   │  1. Check if token needs refresh                            │  │        │
│   │  2. If expired → refresh() via same HTTP stack (observable) │  │        │
│   │  3. Inject: Authorization: Bearer {token}                   │  │        │
│   └─────────────────────────────┬───────────────────────────────┘  │        │
│                                 │                                  │         │
│                                 ▼                                  │         │
│   ┌────────────────────────────────────────────────────────────┐   │        │
│   │ HttpTransport → Platform HTTP Client → Network             │   │        │
│   └─────────────────────────────┬──────────────────────────────┘   │        │
│                                 │                                  │         │
│                                 ▼                                  │         │
│   ┌────────────────────────────────────────────────────────────┐   │        │
│   │ Response received                                          │   │        │
│   │                                                            │   │        │
│   │  On 401: AuthenticatedHttpTransport triggers refresh       │   │        │
│   │          (retry request with new token)                    │   │        │
│   └─────────────────────────────┬──────────────────────────────┘   │        │
│                                 │                                  │         │
│                                 ▼                                  │         │
│   ┌────────────────────────────────────────────────────────────┐   │        │
│   │ ObservableHttpClient                                        │   │        │
│   │                                                             │   │        │
│   │  Emits HttpResponseEvent ────────────────────────────────┐ │   │        │
│   │    • status, headers                                     │ │   │        │
│   │    • body (tokens [REDACTED])                            │ │   │        │
│   └──────────────────────────────────────────────────────────┼─┘   │        │
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
│  ✓ POST {idp}/token (refresh calls go through our HTTP stack)              │
│  ✓ All authenticated API calls (GET /api/v1/rooms, etc.)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                        What is NOT Observable                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  ✗ Authorization request (ASWebAuthenticationSession sandbox)              │
│  ✗ IdP login page (user authentication)                                    │
│  ✗ Code exchange by flutter_appauth (happens inside the library)           │
│                                                                             │
│  Note: With direct OIDC, the initial code exchange is handled internally   │
│  by flutter_appauth and isn't observable. Only token refresh (which we     │
│  trigger manually) goes through our HTTP stack.                            │
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
  final String? idToken;            // Required for OIDC endSession
  final Map<String, dynamic>? userInfo;

  const Authenticated({
    required this.accessToken,
    required this.refreshToken,
    required this.expiresAt,
    required this.issuerId,
    required this.issuerDiscoveryUrl,
    this.idToken,
    this.userInfo,
  });

  bool get isExpired => DateTime.now().isAfter(expiresAt);
  bool get needsRefresh => DateTime.now().isAfter(
    expiresAt.subtract(const Duration(minutes: 1)),
  );
}
```

Note: `userInfo` is intentionally excluded from equality checks as it may be
fetched/updated independently of token state.

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
| `Authenticated.idToken` | `String?` | Propagated from `AuthResult` | `endSession()` - skips IdP logout if null |
| `Authenticated.userInfo` | `Map<String, dynamic>?` | Optionally fetched after auth | Consumers check before use |
| `AuthenticatedHttpClient._getToken()` | `String?` | Returns null when unauthenticated | `_injectAuth()` - skips header if null |

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
| `authProvider` | StateNotifierProvider | Auth state + actions |
| `idpClientProvider` | Provider | IdP token refresh client |

Derived providers (`authCredentialsProvider`, `isAuthenticatedProvider`) added when needed.

### AuthNotifier

```dart
class AuthNotifier extends StateNotifier<AuthState> {
  final FlutterSecureStorage _storage;
  final IdpClient _idpClient;  // For token refresh

  Future<void> signIn(OidcIssuer issuer);
  Future<void> signOut();         // Calls endSession (flutter_appauth) + clears storage
  Future<void> refresh();         // Uses IdpClient (observable via shared HTTP client)
  Future<void> restoreSession();  // On app start
}
```

**signOut behavior:**

- On platforms with flutter_appauth (iOS/macOS): calls `appAuth.endSession()` to end
  the IdP session, then clears local tokens
- On platforms without flutter_appauth (future): clears local tokens only; proper
  endSession support deferred until platform-specific auth is implemented

### IdpClient

Slim client for IdP token operations. Uses the shared HTTP client (observable).

```dart
class IdpClient {
  final HttpClient _httpClient;  // Same client as SoliplexApi

  /// Refresh tokens using IdP token endpoint
  Future<TokenResponse> refreshToken({
    required String tokenEndpoint,
    required String refreshToken,
    required String clientId,
  });
}
```

## Platform Auth Flow

Single file `auth_flow.dart` with platform-appropriate implementation:

### MVP: iOS/macOS (Direct OIDC via flutter_appauth)

Uses `flutter_appauth` with ASWebAuthenticationSession. PKCE handled automatically.

```dart
Future<AuthTokens> authenticate({
  required OidcIssuer issuer,
  required String redirectUri,
}) async {
  // flutter_appauth handles:
  // - PKCE code_verifier/code_challenge generation
  // - State parameter generation and validation
  // - Opening ASWebAuthenticationSession
  // - Code exchange with IdP token endpoint

  final result = await appAuth.authorizeAndExchangeCode(
    AuthorizationTokenRequest(
      issuer.clientId,
      redirectUri, // e.g., 'net.soliplex.app://callback'
      discoveryUrl: '${issuer.serverUrl}/.well-known/openid-configuration',
      scopes: issuer.scope.split(' '),
      preferEphemeralSession: true, // Don't persist browser session
    ),
  );

  if (result == null) {
    throw AuthException('Authentication cancelled or failed');
  }

  return AuthTokens(
    accessToken: result.accessToken!,
    refreshToken: result.refreshToken!,
    expiresAt: result.accessTokenExpirationDateTime!,
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

```dart
redirect: (context, state) {
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
}
```

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
    accessibility: KeychainAccessibility.whenUnlockedThisDeviceOnly,
  ),
  mOptions: MacOsOptions(
    accessibility: KeychainAccessibility.whenUnlockedThisDeviceOnly,
  ),
);
```

This prevents:

- Tokens being restored from backup to another device
- Access when device is locked

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
| Secure token storage | flutter_secure_storage (Keychain) with `whenUnlockedThisDeviceOnly` |
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

- [ ] AuthState.isExpired / needsRefresh
- [ ] Token parsing from callback URI
- [ ] State parameter generation and validation
- [ ] HTTP observer filtering rules

### Widget Tests

- [ ] LoginScreen fetches and renders providers
- [ ] LoginScreen handles loading/error states
- [ ] Auth redirect guard behavior

### Integration Tests

- [ ] Full auth flow on macOS (spike validates this first)
- [ ] Token refresh with artificially short expiry
- [ ] Session restore: write tokens, restart provider, verify state

## File Structure

```text
lib/core/auth/
├── auth_state.dart              # Sealed class (AuthState, Authenticated, etc.)
├── oidc_issuer.dart             # Model from /api/login
├── auth_flow.dart               # Platform auth: authenticate, endSession
├── auth_notifier.dart           # State management + storage
├── idp_client.dart              # Token refresh to IdP
└── authenticated_transport.dart # Token injection, 401 handling

lib/core/providers/
└── auth_provider.dart           # Riverpod providers

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
| AuthState | Sealed class with token fields | ~25 |
| OidcIssuer | Model from /api/login | ~20 |
| AuthNotifier | State management + storage | ~70 |
| auth_flow.dart | authenticate + endSession | ~50 |
| IdpClient | Token refresh to IdP | ~30 |
| authenticated_transport.dart | Token injection, 401 handling | ~50 |
| **Total** | | **~245** |

## Resolved Questions

1. **Auth approach**: Direct OIDC via flutter_appauth (not BFF pattern)
2. **Token refresh**: Via IdpClient using shared HTTP client (observable)
3. **HTTP client architecture**: Single HTTP client, ObservableHttpClient wraps it, both SoliplexApi and IdpClient use it
4. **Logout**: Full OIDC logout via `endSession` on platforms with flutter_appauth (iOS/macOS); local-only logout on other platforms until proper auth is implemented
5. **Multiple providers**: Support one at a time (can switch by logging out first)
6. **Auth observability**: Browser flow not observable; refresh calls are observable
7. **Platform scope**: MVP = macOS + iOS; Desktop/Web deferred
8. **Keychain security**: `whenUnlockedThisDeviceOnly` to prevent backup/restore attacks
9. **Startup UX**: Loading indicator until auth state resolves
10. **refreshExpiresAt**: Omitted - let `invalid_grant` signal refresh token expiry

## Deferred Items

- Windows/Linux loopback server implementation (includes endSession support)
- Web redirect flow and memory-only storage (includes RP-Initiated Logout)
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

### Slice 2 Status: ⏳ Not Started

### Slice 3 Status: ⏳ Not Started
