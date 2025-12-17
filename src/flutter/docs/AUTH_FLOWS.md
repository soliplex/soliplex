# Authentication Flows

## Overview

SOLIPLEX supports OIDC authentication via Keycloak (or compatible OIDC providers) with platform-specific flows optimized for each deployment target.

| Platform | Flow | Library |
|----------|------|---------|
| Web | Backend-mediated OAuth | Custom implementation |
| iOS | Direct PKCE | flutter_appauth (ASWebAuthenticationSession) |
| Android | Direct PKCE | flutter_appauth (Chrome Custom Tabs) |
| macOS | Direct PKCE | flutter_appauth |
| Desktop | Direct PKCE | flutter_appauth |

## Configuration

### Backend Configuration

Authentication providers are configured in the Soliplex backend. The frontend discovers available providers via `GET /api/login`.

Example backend configuration (`config.yaml`):

```yaml
oidc_auth_systems:
  - id: "keycloak"
    title: "Sign in with Keycloak"
    server_url: "https://keycloak.example.com/realms/myrealm"
    client_id: "soliplex-client"
    scope: "openid profile email"
```

### Flutter App Configuration

The app auto-discovers providers via `GET /api/login`. No app-side OIDC configuration is needed.

**Platform-specific redirect URIs:**
- Web: `/` (hash-based routing - tokens arrive at `/?token=...`)
- Mobile/desktop: `ai.soliplex.client://callback`

### Keycloak Client Configuration

Register the following redirect URIs in your Keycloak client:

| Platform | Redirect URI |
|----------|-------------|
| Web (production) | `https://your-backend.com/api/auth/{system}` |
| Web (development) | `http://localhost:8000/api/auth/{system}` |
| iOS/Android | `ai.soliplex.client://callback` |
| Desktop | `ai.soliplex.client://callback` |

Note: The backend's OAuth callback is at `/api/auth/{system}`. After exchanging the code for tokens, the backend redirects to the frontend's `return_to` URL (which is `/`) with tokens in query params.

**Keycloak Client Settings:**
- Client Protocol: `openid-connect`
- Access Type: `public` (no client secret needed with PKCE)
- Standard Flow Enabled: `ON`
- PKCE Code Challenge Method: `S256` (for mobile/desktop)

### Custom URL Scheme (Mobile/Desktop)

The custom URL scheme `ai.soliplex.client` is configured in platform-specific files:

| Platform | Configuration File |
|----------|-------------------|
| Android | `android/app/src/main/AndroidManifest.xml` |
| iOS | `ios/Runner/Info.plist` |
| macOS | `macos/Runner/Info.plist` |

## Web Authentication Flow (Backend-Mediated)

Web browsers cannot perform OAuth token exchange directly due to CORS restrictions. The backend mediates the entire OAuth flow.

### Why Backend-Mediated?

1. **CORS**: Browsers block cross-origin POST requests to Keycloak's token endpoint
2. **Security**: Client secrets can stay server-side
3. **Simplicity**: Frontend code is simpler without PKCE implementation

### Flow Sequence

```
┌──────────────┐     ┌───────────────┐     ┌──────────────┐     ┌───────────────┐
│  Flutter App │     │    Backend    │     │   Keycloak   │     │     User      │
└──────┬───────┘     └───────┬───────┘     └──────┬───────┘     └───────┬───────┘
       │                     │                    │                     │
       │  1. GET /api/login  │                    │                     │
       │────────────────────>│                    │                     │
       │  (discover providers)                    │                     │
       │<────────────────────│                    │                     │
       │                     │                    │                     │
       │  2. Redirect to:    │                    │                     │
       │  /api/login/{system}│                    │                     │
       │  ?return_to=...     │                    │                     │
       │────────────────────>│                    │                     │
       │                     │                    │                     │
       │                     │  3. OAuth redirect │                     │
       │                     │───────────────────>│                     │
       │                     │                    │  4. Login page      │
       │                     │                    │────────────────────>│
       │                     │                    │                     │
       │                     │                    │<────────────────────│
       │                     │                    │  5. Credentials     │
       │                     │                    │                     │
       │                     │  6. Auth code      │                     │
       │                     │<───────────────────│                     │
       │                     │                    │                     │
       │                     │  7. Exchange code  │                     │
       │                     │   for tokens       │                     │
       │                     │───────────────────>│                     │
       │                     │<───────────────────│                     │
       │                     │  8. Tokens         │                     │
       │                     │                    │                     │
       │  9. Redirect to:    │                    │                     │
       │  /auth/callback?    │                    │                     │
       │  token=...          │                    │                     │
       │<────────────────────│                    │                     │
       │                     │                    │                     │
       │  10. Extract tokens │                    │                     │
       │  from URL, store    │                    │                     │
       │  securely           │                    │                     │
       │                     │                    │                     │
```

### Backend Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `GET /api/login` | Discover available OIDC providers |
| `GET /api/login/{system}?return_to=...` | Initiate OAuth flow |
| `GET /api/auth/{system}` | OAuth callback - backend receives auth code, exchanges for tokens, redirects to `return_to` with tokens |

### Web Callback Flow (Hash-Based Routing)

1. Frontend redirects to `/api/login/{system}?return_to=/`
2. Backend redirects to OIDC provider
3. User authenticates
4. OIDC provider redirects to backend callback (`/api/auth/{system}`)
5. Backend exchanges code for tokens
6. Backend redirects to `return_to` URL with tokens as query params:
   ```
   /?token={access_token}&refresh_token={refresh_token}&expires_in={seconds}
   ```
7. Flutter app detects tokens, redirects to `/#/auth/callback?token=...`
8. AuthCallbackScreen processes and stores tokens, navigates to `/#/chat`

### Key Files

| File | Purpose |
|------|---------|
| `lib/core/services/auth_manager.dart` | Builds redirect URL (`/api/auth/{system}` for web) |
| `lib/core/auth/oidc_auth_interactor.dart` | `OidcWebAuthInteractor` - initiates backend redirect |
| `lib/core/auth/web_auth_callback_handler.dart` | Handles callback, extracts tokens |
| `lib/core/auth/web_auth_callback_web.dart` | Detects `/api/auth/{system}` callback URL, extracts params |
| `lib/core/auth/callback_params.dart` | Callback parameter types |
| `lib/core/router/app_router.dart` | Routes `/api/auth/:system` to `AuthCallbackScreen` |

## Mobile/Desktop Authentication Flow (Direct PKCE)

Native platforms use `flutter_appauth` for direct OAuth with the OIDC provider using PKCE (Proof Key for Code Exchange).

### Why Direct PKCE?

1. **No CORS**: Native OS layers bypass browser restrictions
2. **Security**: PKCE prevents authorization code interception
3. **UX**: System browser with credential managers, biometric auth

### Flow Sequence

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐     ┌───────────────┐
│  Flutter App │     │   flutter_appauth │     │   Keycloak   │     │     User      │
└──────┬───────┘     └────────┬─────────┘     └──────┬───────┘     └───────┬───────┘
       │                      │                      │                     │
       │  1. authorizeAndExchangeCode()              │                     │
       │─────────────────────>│                      │                     │
       │                      │                      │                     │
       │                      │  2. Auth URL +       │                     │
       │                      │     PKCE challenge   │                     │
       │                      │─────────────────────>│                     │
       │                      │                      │  3. Login page      │
       │                      │                      │────────────────────>│
       │                      │                      │                     │
       │                      │                      │<────────────────────│
       │                      │                      │  4. Credentials     │
       │                      │                      │                     │
       │                      │  5. Auth code via    │                     │
       │                      │  custom URL scheme   │                     │
       │                      │<─────────────────────│                     │
       │                      │                      │                     │
       │                      │  6. Exchange code    │                     │
       │                      │  + PKCE verifier     │                     │
       │                      │─────────────────────>│                     │
       │                      │<─────────────────────│                     │
       │                      │  7. Tokens           │                     │
       │                      │                      │                     │
       │  8. Token response   │                      │                     │
       │<─────────────────────│                      │                     │
       │                      │                      │                     │
       │  9. Store tokens     │                      │                     │
       │                      │                      │                     │
```

### PKCE Security

PKCE (RFC 7636) protects against authorization code interception:

1. **Code Verifier**: 64-byte random string generated by app
2. **Code Challenge**: `BASE64URL(SHA256(code_verifier))` sent to auth server
3. **Verification**: Token endpoint requires `code_verifier` matching the challenge

### Key Files

| File | Purpose |
|------|---------|
| `lib/core/auth/oidc_auth_interactor.dart` | `OidcMobileAuthInteractor` - uses flutter_appauth |
| `lib/core/auth/pkce_utils.dart` | PKCE challenge generation |

## Token Storage

Tokens are stored securely using platform-appropriate mechanisms:

| Platform | Storage Mechanism |
|----------|------------------|
| iOS | Keychain |
| Android | EncryptedSharedPreferences |
| macOS | Keychain |
| Web | localStorage (same-origin protected) |

### Stored Values

| Key | Value |
|-----|-------|
| `oidc.access` | Access token |
| `oidc.refresh` | Refresh token |
| `oidc.id` | ID token |
| `oidc.expiration` | Expiration timestamp (milliseconds) |

### SSO Config Storage

Per-server SSO configuration is stored with keys like `sso.{serverId}.{field}`:

| Key Pattern | Purpose |
|-------------|---------|
| `sso.{serverId}.id` | Provider ID |
| `sso.{serverId}.endpoint` | OIDC issuer URL |
| `sso.{serverId}.tokenEndpoint` | Token endpoint URL |
| `sso.{serverId}.clientId` | OAuth client ID |
| `sso.{serverId}.scopes` | Comma-separated scopes |

## Token Refresh

Both platforms refresh tokens automatically before API calls when expiring within 5 minutes.

**Web**: POST to backend's token refresh proxy (avoids CORS)
**Mobile**: `flutter_appauth.token()` native call

### Refresh Flow

1. Check if current token expires within 5 minutes
2. Use stored refresh token to get new access token
3. Update stored tokens
4. Continue with API call

## Logout

### Web Logout

1. Clear stored tokens locally first (to ensure session termination)
2. Redirect browser to OIDC provider's logout endpoint (front-channel)
   - Parameters:
     - `post_logout_redirect_uri`: Back to app (must be absolute URI)
     - `id_token_hint`: Included if available (backend flow may omit this)
     - `client_id`: Fallback if `id_token_hint` is missing
3. OIDC provider clears session cookies
4. OIDC provider redirects back to application (or shows logout confirmation)

### Mobile Logout

1. Call `flutter_appauth.endSession()` to invalidate session
2. Clear stored tokens locally
3. Navigate to login screen

## Troubleshooting

### Web: "CORS error" on token exchange

**Cause**: App is attempting direct PKCE flow instead of backend-mediated.

**Solution**: Ensure `OidcWebAuthInteractor` is used (not mobile interactor). Check that `kIsWeb` detection is working correctly.

### Mobile: "Invalid redirect URI"

**Cause**: Custom URL scheme not registered or mismatched.

**Solution**:
1. Verify `ai.soliplex.client://callback` is in Keycloak's valid redirect URIs
2. Check platform-specific configuration (AndroidManifest.xml, Info.plist)

### "State mismatch" error

**Cause**: Authentication session expired (5 minute TTL) or CSRF detected.

**Solution**: Try authentication again. If persistent, check for clock skew between client and server.

### "No pending authentication" error

**Cause**: App was restarted during auth flow, or storage was cleared.

**Solution**: Start authentication flow again.

### Token refresh failing

**Cause**: Refresh token expired or revoked.

**Solution**: Re-authenticate to get new tokens.

## Security Considerations

### Web-Specific

- Tokens appear briefly in URL during callback (cleared immediately)
- Access logs may capture token values - use short-lived tokens
- localStorage is same-origin protected but vulnerable to XSS

### Mobile-Specific

- Custom URL schemes can be intercepted by malicious apps - mitigated by PKCE
- Keychain/Keystore provides hardware-backed security when available

### General

- Always use HTTPS in production
- Keep access tokens short-lived (5-15 minutes recommended)
- Refresh tokens should have reasonable expiration (hours to days)
- Validate tokens server-side on every API request
