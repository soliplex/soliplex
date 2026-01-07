# Backend-Frontend Integration Notes

This document tracks backend changes needed for web platform support, organized by
priority.

## Quick Reference: Backend Changes Needed

### 🚫 BLOCKING - Web Platform Non-Functional Without These

| Change | Endpoint | Description |
|--------|----------|-------------|
| **BFF Token Refresh** | `POST /api/refresh` | Proxy refresh requests to IdP (CORS blocks direct calls) |

### 🔒 SECURITY - Recommended for Production

| Change | Endpoint | Description |
|--------|----------|-------------|
| **OAuth State Parameter** | `/api/login/{provider}` | Echo `state` param for CSRF protection |
| **Fragment-based Tokens** | Callback redirect | Use `#token=` instead of `?token=` |

### ✨ CONVENIENCE - Simplifies Frontend Code

| Change | Endpoint | Description |
|--------|----------|-------------|
| **Include id_token** | Callback redirect | Enables proper OIDC logout |
| **Include Issuer Metadata** | Callback redirect | Removes need for PreAuthState storage |

---

## API Specifications

### 1. BFF Token Refresh Endpoint (BLOCKING)

**Status**: ❌ Missing - Web auth broken without this

**Why needed**: Frontend cannot call IdP token endpoint directly due to CORS. Browsers
block cross-origin requests to `https://pydio-kc.enfoldsystems.net/...` from the
frontend origin.

**Error without this**:

```text
Access to fetch at 'https://pydio-kc.../token' from origin 'http://localhost:...'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header
```

**Specification**:

```text
POST /api/refresh
Content-Type: application/json

Request:
{
  "refresh_token": "eyJhbGci..."
}

Response (success):
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",   // New refresh token if rotated
  "expires_in": 3600,
  "token_type": "Bearer"
}

Response (error - invalid/expired refresh token):
HTTP 401
{
  "error": "invalid_grant",
  "error_description": "Refresh token expired"
}

Response (error - other):
HTTP 500
{
  "error": "server_error",
  "error_description": "..."
}
```

**Backend implementation**:

1. Extract `refresh_token` from request body
2. Call IdP token endpoint server-side:

   ```text
   POST https://{idp}/protocol/openid-connect/token
   Content-Type: application/x-www-form-urlencoded

   grant_type=refresh_token&
   refresh_token={refresh_token}&
   client_id={client_id}&
   client_secret={client_secret}  // If confidential client
   ```

3. Return IdP response to frontend (or transform errors)

**Frontend changes when ready**:

- `packages/soliplex_client/lib/src/auth/token_refresh_service.dart`
- `lib/core/auth/auth_notifier.dart`

---

### 2. OAuth State Parameter Echo (SECURITY)

**Status**: ⚠️ Missing - CSRF vulnerability (CAT II)

**Current behavior**: BFF ignores any `state` parameter in the OAuth flow.

**Why needed**: OAuth 2.0 RFC 6749 Section 10.12 requires `state` for CSRF protection.
Without it, an attacker could:

1. Start OAuth flow on their own device
2. Get the callback URL with tokens
3. Trick victim into visiting that URL
4. Victim's session now uses attacker's account

**Specification**:

```text
Current:
  GET /api/login/pydio?return_to=https://app.example.com/callback
  → Redirects to IdP
  → IdP redirects to: https://app.example.com/callback?token=xxx

With state:
  GET /api/login/pydio?return_to=https://app.example.com/callback&state=abc123
  → Redirects to IdP with state=abc123
  → IdP redirects to: https://app.example.com/callback?token=xxx&state=abc123
```

**Backend implementation**:

1. Accept `state` parameter in `/api/login/{provider}`
2. Include `state` in redirect to IdP
3. Echo `state` in callback redirect URL

**Frontend changes when ready**:

- `lib/core/auth/auth_flow_web.dart` - Generate cryptographic state
- `lib/core/auth/auth_notifier.dart` - Validate state in callback

---

### 3. Fragment-Based Token Delivery (SECURITY)

**Status**: ⚠️ Current method exposes tokens (CAT III)

**Current behavior**: Tokens in URL query string `?token=xxx` are:

- Visible in browser address bar for ~1-2 seconds
- Stored in browser history
- Potentially sent in Referer headers

**Why needed**: URL fragments (`#token=xxx`) are:

- Never sent in HTTP requests (including Referer)
- Not stored in browser history in the same way
- Cleared faster by frontend code

**Specification**:

```text
Current:
  Redirect to: https://app.example.com/?token=xxx&refresh_token=yyy

With fragments:
  Redirect to: https://app.example.com/#access_token=xxx&refresh_token=yyy&expires_in=3600
```

**Note**: This follows the OAuth 2.0 Implicit Flow response format, which is well-understood
by frontend libraries.

**Frontend changes when ready**:

- `lib/core/auth/web_auth_callback_web.dart` - Extract from fragment
- `lib/core/auth/callback_params.dart` - Update parameter model

---

### 4. Include id_token in Callback (CONVENIENCE)

**Status**: ⚠️ Missing - Logout doesn't terminate IdP session

**Current behavior**: BFF callback only returns `token`, `refresh_token`, `expires_in`.
No `id_token` is provided.

**Why needed**: OIDC logout (`end_session_endpoint`) requires `id_token_hint` to properly
terminate the IdP session. Without it:

- User clicks "Logout" in app
- App clears local tokens
- User visits app again
- IdP auto-logs them in (session still active)

**Specification**:

```text
Current:
  ?token=xxx&refresh_token=yyy&expires_in=3600

With id_token:
  ?token=xxx&refresh_token=yyy&expires_in=3600&id_token=zzz
```

**Frontend changes when ready**:

- `lib/core/auth/callback_params.dart` - Add `idToken` field
- `lib/core/auth/auth_flow_web.dart` - Use for `endSession()`

---

### 5. Include Issuer Metadata in Callback (CONVENIENCE)

**Status**: ⚠️ Missing - Frontend uses complex workaround

**Current behavior**: Frontend must:

1. Store issuer info in localStorage before OAuth redirect (`PreAuthState`)
2. Set 5-minute expiry for security
3. Load and validate after callback
4. Clean up storage

**Why needed**: Simplifies frontend significantly. Frontend needs issuer metadata
(discovery URL, client ID) for token refresh.

**Specification**:

```text
Current:
  ?token=xxx&refresh_token=yyy&expires_in=3600

With metadata:
  ?token=xxx&refresh_token=yyy&expires_in=3600&issuer_id=pydio&discovery_url=https://...&client_id=xxx
```

**Alternative**: If implementing BFF refresh endpoint (#1), this becomes less important
since the backend handles refresh internally.

**Frontend changes when ready**:

- `lib/core/auth/callback_params.dart` - Add issuer fields
- `lib/core/auth/auth_notifier.dart` - Remove PreAuthState handling
- `lib/core/auth/auth_storage.dart` - Remove PreAuthState methods

---

## Current Frontend Workarounds

| Issue | Workaround | Limitation |
|-------|------------|------------|
| Token refresh CORS | None | ❌ Web auth broken after token expires |
| CSRF (no state) | PreAuthState with 5-min expiry | Narrow attack window remains |
| Tokens in URL | Clear via `replaceState()` in main() | ~1-2s visibility during load |
| No id_token | Skip IdP logout | Users auto-login on return |
| No issuer metadata | PreAuthState localStorage | Complex code, expiry handling |

---

## Summary Table

| Issue | Priority | Security | Frontend Impact | Backend Effort |
|-------|----------|----------|-----------------|----------------|
| No BFF refresh | **BLOCKING** | N/A | Broken | Medium |
| No state param | Security | CAT II | Workaround exists | Low |
| Tokens in query | Security | CAT III | Workaround exists | Medium |
| No id_token | Convenience | None | Workaround exists | Low |
| No issuer metadata | Convenience | None | Complex workaround | Low |

---

## References

- OAuth 2.0 RFC 6749: <https://datatracker.ietf.org/doc/html/rfc6749>
- OAuth 2.0 Security BCP: <https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics>
- OIDC Core 1.0: <https://openid.net/specs/openid-connect-core-1_0.html>
- OWASP CSRF Prevention: <https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html>
