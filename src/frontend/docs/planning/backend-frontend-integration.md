# Backend-Frontend Integration Notes

This document tracks backend limitations that affect the frontend implementation,
and opportunities where backend changes would simplify the frontend.

## Current Backend Limitations

### 1. OAuth State Parameter Not Echoed (CAT II Security)

**Location**: BFF OAuth flow (`/api/login/{provider}`)

**Issue**: The BFF doesn't generate or echo an OAuth `state` parameter in the callback.
OAuth 2.0 RFC 6749 Section 10.12 recommends a cryptographically random `state` parameter
bound to the user's session for CSRF protection.

**Frontend Workaround**: Uses time-limited `PreAuthState` (5-minute expiry) stored in
localStorage before redirect. This provides partial CSRF protection but is not as robust
as proper state parameter validation.

**Impact**: Narrow window (5 minutes) for login CSRF attacks. An attacker could initiate
an OAuth flow, then trick a victim into completing auth with the attacker's account within
the time window.

**Backend Change to Simplify**: Generate a cryptographic nonce, include it in the redirect
URL as `state` parameter, and echo it back in the callback URL. Frontend would then:

1. Generate state locally and include in `return_to` URL
2. BFF echoes state in callback
3. Frontend validates state matches before accepting tokens

Files affected if backend is updated:

- `lib/core/auth/auth_flow_web.dart` - Add state parameter generation
- `lib/core/auth/auth_notifier.dart` - Validate state in `completeWebAuth()`
- `lib/core/auth/auth_storage.dart` - Store state alongside PreAuthState

### 2. Tokens Delivered via URL Query Parameters (CAT III)

**Location**: BFF callback redirect

**Issue**: The BFF returns tokens in URL query parameters (`?token=xxx&refresh_token=xxx`).
This briefly exposes tokens in:

- Browser address bar
- Browser history (until cleanup)
- Potential referrer headers
- Browser extensions observing URL changes

**Frontend Workaround**: Immediately calls `replaceState()` to remove tokens from browser
history. CSP blocks external resources that could leak referrer.

**Backend Change to Simplify**: Use one of:

1. **Fragment-based delivery** (`#access_token=`) - Fragments aren't sent in referrers
2. **POST to callback** - Tokens in request body, not URL
3. **Authorization code flow** - Return code in URL, exchange for tokens via POST

Files affected if backend is updated:

- `lib/core/auth/web_auth_callback_web.dart` - Update token extraction logic
- `lib/core/auth/callback_params.dart` - Update parameter model

### 3. No id_token in Web BFF Flow

**Location**: BFF token response

**Issue**: The BFF doesn't return `id_token` in the callback. OIDC logout requires
`id_token_hint` to properly terminate the IdP session.

**Frontend Workaround**: Uses empty string for `idToken` on web. Web logout only clears
local tokens without redirecting to IdP's `end_session_endpoint`.

**Impact**: Users remain logged into the IdP even after "logging out" of the app. If
they visit the login page again, they may be auto-logged-in without re-entering
credentials.

**Backend Change to Simplify**: Include `id_token` in the callback redirect. Frontend
would store it and use for proper OIDC logout.

Files affected if backend is updated:

- `lib/core/auth/callback_params.dart` - Add `idToken` field to `WebCallbackParams`
- `lib/core/auth/auth_notifier.dart` - Store id_token from callback
- `lib/core/auth/auth_flow_web.dart` - Implement `endSession()` with id_token_hint

### 4. Issuer Metadata Not in Callback

**Location**: BFF callback redirect

**Issue**: The BFF callback only includes tokens (`token`, `refresh_token`, `expires_in`,
`error`, `error_description`). It doesn't include issuer metadata needed for token
refresh (issuer ID, discovery URL, client ID).

**Frontend Workaround**: Saves `PreAuthState` (issuer metadata) to localStorage before
redirect. After callback, loads PreAuthState to get issuer info needed for refresh.

**Complexity**: Requires two storage operations, expiry checking, and cleanup logic.
Creates the "duplicate expiry check" pattern that was recently refactored.

**Backend Change to Simplify**: Include issuer metadata in callback:

```text
?token=xxx&refresh_token=xxx&expires_in=xxx&issuer_id=xxx&discovery_url=xxx&client_id=xxx
```

Or return a signed/encrypted blob that frontend can pass back for refresh.

Files affected if backend is updated:

- `lib/core/auth/callback_params.dart` - Add issuer fields
- `lib/core/auth/auth_notifier.dart` - Remove PreAuthState handling
- `lib/core/auth/auth_storage.dart` - Remove PreAuthState methods
- `lib/core/auth/auth_storage_web.dart` - Remove PreAuthState storage

## Summary Table

| Limitation | Security Impact | Frontend Complexity | Backend Fix Effort |
|------------|-----------------|--------------------|--------------------|
| No state parameter | CAT II (CSRF) | Medium | Low - add state echo |
| Tokens in URL | CAT III | Low (cleanup works) | Medium - change delivery |
| No id_token | User confusion | Low | Low - include in response |
| No issuer metadata | None | High | Low - include in response |

## Recommendation Priority

1. **State parameter** (security improvement + simplifies frontend)
2. **Issuer metadata in callback** (simplifies frontend significantly)
3. **id_token in callback** (enables proper logout)
4. **Token delivery method** (defense-in-depth, current mitigation adequate)

## Acceptance Criteria for Backend Changes

If backend team implements these changes:

### State Parameter

- BFF generates cryptographic random state (min 32 bytes, base64url encoded)
- State included in redirect to IdP
- State echoed in callback URL as `state` parameter
- Frontend validates state matches before accepting tokens

### Issuer Metadata

- Callback includes `issuer_id`, `discovery_url`, `client_id` parameters
- Values match what was passed to `/api/login/{provider}`
- Frontend can use directly without PreAuthState lookup

### id_token

- Callback includes `id_token` parameter when available from IdP
- Frontend stores and uses for `end_session_endpoint` redirect

## References

- OAuth 2.0 Security BCP: <https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics>
- OIDC Core 1.0 Section 12.2 (id_token in refresh): <https://openid.net/specs/openid-connect-core-1_0.html#RefreshTokenResponse>
- OWASP CSRF Prevention: <https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html>
