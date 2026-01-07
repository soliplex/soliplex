# Plan: Enable Web Platform Support

## Summary

Enable the Soliplex Flutter frontend to run on web with all current features,
including OIDC authentication.

## Context

The current app supports iOS/macOS using `flutter_appauth` for direct OIDC flow.
Web requires a different approach:

1. `flutter_appauth` uses `dart:ffi` - unavailable on web
1. `cupertino_http` uses `dart:ffi` - unavailable on web
1. CORS restrictions prevent direct OIDC token exchange from browser
1. `dart:io` exceptions (SocketException, HttpException) don't exist on web

**Good news**: The backend already provides BFF endpoints for web OAuth:

- `GET /api/login/{provider}?return_to={url}` - Initiates OAuth (backend handles PKCE)
- `GET /api/auth/{provider}` - Callback that redirects with tokens in URL

Reference implementation: `/Users/jaeminjo/enfold/clean_soliplex/src/flutter/lib/core/auth/`

## Token Storage Decision

Per sentinel security review + clean_soliplex reference implementation:

- **Use localStorage** (matching clean_soliplex) - tokens persist across sessions
- **Store refresh tokens** - enables automatic token refresh on web
- **Token refresh via direct HTTP POST** to OIDC token endpoint (same as native)

**Security mitigations (already in place or backend responsibility):**

- CSP headers to block XSS
- Server-side token validation
- Token refresh buffer (5 min before expiry)
- Logout clears all tokens

**Why localStorage over sessionStorage**: XSS can access both equally. sessionStorage
loses tokens on tab close, breaking legitimate workflows (accidental refresh, new tab).
For an internal tool where we control the codebase, localStorage is pragmatic.

## Implementation Slices

### Slice 1: Web Platform Configuration

Enable `flutter build web` so all subsequent work can be verified.

**Files to create/modify:**

1. `web/index.html` - Flutter web entry point (if not exists, Flutter creates it)
1. `pubspec.yaml` - Add web dependency:

```yaml
dependencies:
  web: ^1.1.0
```

**Verification:** `flutter build web` compiles (will fail on dart:io - that's expected)

---

### Slice 2: CORS Verification

Before investing in auth work, verify backend CORS is configured.

**Manual test:**

1. Run `flutter run -d chrome`
1. Check browser console for CORS errors on API calls
1. If CORS errors: backend needs `Access-Control-Allow-Origin` header for web origin

**If CORS fails:** Stop and configure backend before proceeding.

---

### Slice 3: HTTP Layer Web Compatibility

Fix `dart:io` dependencies that break web compilation.

#### Why web compilation fails

When `flutter build web` runs, Dart compiles all exported code - even code the app
never calls. The export chain causes the problem:

```text
soliplex_client_native.dart
  → exports src/clients/clients.dart
    → exports cupertino_http_client.dart
      → imports package:cupertino_http
        → uses dart:ffi
          → FAILS on web (dart:ffi unavailable)
```

#### Why no stub file is needed

We investigated whether app code directly references `CupertinoHttpClient`:

```bash
grep -r "CupertinoHttpClient" lib/
# Result: No matches found
```

**Findings:**

- App code uses `createPlatformClient()` which returns `SoliplexHttpClient` interface
- `createPlatformClient()` already handles web via `create_platform_client_stub.dart`
  (returns `DartHttpClient` on web)
- Direct `CupertinoHttpClient` references exist only in:
  - Package internals (`create_platform_client_io.dart` - already conditionally imported)
  - Tests (run on native platforms, not web)
  - Documentation

**Conclusion:** We don't need a stub class. Simply don't export `CupertinoHttpClient`
on web. Code that incorrectly tries to import it directly will get a compile error,
which is the correct behavior - it guides developers to use `createPlatformClient()`.

#### Files to modify

1. `packages/soliplex_client_native/lib/src/clients/clients.dart`
   - Add conditional export so `CupertinoHttpClient` is only available on IO platforms:

   ```dart
   // Before:
   export 'cupertino_http_client.dart';

   // After - only export on platforms with dart:io
   export 'cupertino_http_client.dart'
       if (dart.library.io) 'cupertino_http_client.dart';
   ```

   On web, this exports nothing. That's correct because:
   - Web code should use `createPlatformClient()` → returns `DartHttpClient`
   - Direct `CupertinoHttpClient` usage would fail anyway (no NSURLSession on web)

1. `packages/soliplex_client/lib/src/http/dart_http_client.dart`
   - Remove `import 'dart:io'`
   - Replace `SocketException`/`HttpException` catches with platform-agnostic pattern:

   ```dart
   // Before: catches dart:io exceptions
   } on SocketException catch (e, stackTrace) { ... }
   } on HttpException catch (e, stackTrace) { ... }

   // After: generic fallback works on all platforms
   } on http.ClientException catch (e, stackTrace) {
     throw NetworkException(
       message: 'Client error: ${e.message}',
       originalError: e,
       stackTrace: stackTrace,
     );
   } on Exception catch (e, stackTrace) {
     // Generic fallback for platform-specific exceptions (SocketException on
     // native, browser exceptions on web)
     throw NetworkException(
       message: 'Network error: $e',
       originalError: e,
       stackTrace: stackTrace,
     );
   }
   ```

1. **Audit `RefreshingHttpClient`** for dart:io usage - apply same fix if needed

**Verification:** `flutter build web` succeeds

---

### Slice 4: Platform-Aware Auth Storage

Make `AuthStorage` platform-aware instead of creating a separate `TokenStorage` layer.
(Per blacksmith review: 3 files instead of 5, preserves existing high-level API)

**Files to create:**

1. `lib/core/auth/auth_storage_native.dart` (NEW)
   - Native implementation using `flutter_secure_storage`
   - Move existing `AuthStorage` logic here
   - Keychain config for iOS/macOS

1. `lib/core/auth/auth_storage_web.dart` (NEW)
   - Web implementation using localStorage
   - Same API as native: `saveTokens()`, `loadTokens()`, `clearTokens()`
   - Add comment explaining why localStorage is acceptable (security decision)

**Files to modify:**

1. `lib/core/auth/auth_storage.dart`
   - Convert to abstract interface + factory with conditional import:

   ```dart
   import 'auth_storage_native.dart'
       if (dart.library.js_interop) 'auth_storage_web.dart' as impl;

   abstract class AuthStorage {
     factory AuthStorage() => impl.createAuthStorage();

     Future<void> saveTokens(Authenticated state);
     Future<Authenticated?> loadTokens();
     Future<void> clearTokens();
     Future<void> clearOnReinstall(); // no-op on web
   }
   ```

**Verification:**

- Existing auth tests still pass
- Manual test: login on native still works

---

### Slice 5: Web Authentication Flow

Implement BFF-pattern authentication for web.

**Files to create:**

1. `lib/core/auth/auth_flow_native.dart` (NEW)
   - Move existing `flutter_appauth` code here
   - Contains `authenticate()` and `endSession()`

1. `lib/core/auth/auth_flow_web.dart` (NEW)
   - Web implementation using BFF pattern
   - `authenticate()`: redirects to `/api/login/{provider}?return_to=/auth/callback`
   - `endSession()`: clears local tokens (no IdP logout on web)

1. `lib/core/auth/web_auth_callback_web.dart` (NEW)
   - Extracts tokens from URL using `web` package
   - **Error handling** (per blacksmith):

     ```dart
     // Check for OAuth errors first
     final error = queryParams['error'];
     if (error != null) {
       throw AuthException('OAuth error: $error - ${queryParams['error_description']}');
     }
     // Validate required tokens exist
     final token = queryParams['token'];
     if (token == null) {
       throw AuthException('Missing token in callback');
     }
     ```

   - **Clean URL after extraction** (per pathfinder - security):

     ```dart
     // Remove tokens from browser history
     html.window.history.replaceState(null, '', '/');
     ```

1. `lib/core/auth/web_auth_callback_stub.dart` (NEW)
   - No-op for native platforms

1. `lib/features/auth/auth_callback_screen.dart` (NEW)
   - Route handler for `/auth/callback`
   - Extracts tokens, stores them, navigates to home

**Files to modify:**

1. `lib/core/auth/auth_flow.dart`
   - Convert to conditional import dispatcher:

   ```dart
   import 'auth_flow_native.dart'
       if (dart.library.js_interop) 'auth_flow_web.dart' as impl;

   Future<AuthResult> authenticate(OidcIssuer issuer) => impl.authenticate(issuer);
   Future<void> endSession(...) => impl.endSession(...);
   ```

1. `lib/core/auth/auth_notifier.dart`
   - Add `completeWebAuth(CallbackParams params)` method for callback handling

1. `lib/core/router/app_router.dart`
   - Add `/auth/callback` route
   - **Important**: This route must bypass auth guard (chicken-and-egg problem)

**Verification:**

- Native auth still works
- Web auth flow completes (requires running backend)

---

### Slice 6: Testing & Validation

Specific test matrix (per pathfinder):

**Compilation:**

- [ ] `flutter build web` succeeds with no errors
- [ ] `flutter build macos` still succeeds
- [ ] `flutter build ios` still succeeds

**Unit tests:**

- [ ] All existing auth tests pass
- [ ] `AuthStorage` factory returns correct implementation per platform

**Native regression (manual):**

- [ ] Login works on macOS
- [ ] Token refresh works on macOS
- [ ] Logout works on macOS

**Web auth flow (manual):**

- [ ] Login redirects to backend OAuth endpoint
- [ ] OAuth callback extracts tokens correctly
- [ ] Tokens stored in localStorage
- [ ] Token refresh works
- [ ] Logout clears localStorage
- [ ] OAuth error shows user-friendly message
- [ ] Direct navigation to `/auth/callback` shows error (not crash)
- [ ] Tokens removed from URL after extraction (check browser history)

**Web features (manual):**

- [ ] Chat works (messages send/receive)
- [ ] SSE streaming works (AG-UI events)
- [ ] Thread switching works
- [ ] Room navigation works

---

## Critical Files Summary

| File | Action |
|------|--------|
| `packages/soliplex_client_native/.../clients.dart` | Add conditional export (no stub needed) |
| `packages/soliplex_client/lib/src/http/dart_http_client.dart` | Remove dart:io |
| `lib/core/auth/auth_storage.dart` | Convert to interface + factory |
| `lib/core/auth/auth_storage_native.dart` | NEW - flutter_secure_storage impl |
| `lib/core/auth/auth_storage_web.dart` | NEW - localStorage impl |
| `lib/core/auth/auth_flow.dart` | Convert to conditional import dispatcher |
| `lib/core/auth/auth_flow_native.dart` | NEW - flutter_appauth impl |
| `lib/core/auth/auth_flow_web.dart` | NEW - BFF redirect impl |
| `lib/core/auth/web_auth_callback_web.dart` | NEW - URL token extraction |
| `lib/features/auth/auth_callback_screen.dart` | NEW - callback route |
| `lib/core/router/app_router.dart` | Add /auth/callback route |

## Dependencies to Add

```yaml
dependencies:
  web: ^1.1.1  # For web platform APIs (localStorage, window.location)
```

## Estimated LOC

- ~30 lines: Web config + dependencies
- ~20 lines: HTTP conditional export + exception fix (no stub file needed)
- ~80 lines: Auth storage (interface + 2 implementations)
- ~120 lines: Web auth flow + callback handling
- ~30 lines: Router changes
- **Total: ~280 lines**

## Questions Resolved

1. **Token storage**: localStorage with refresh tokens (per clean_soliplex + sentinel review)
1. **PKCE handling**: Backend handles PKCE for web (BFF pattern)
1. **Token refresh**: Direct HTTP POST to OIDC token endpoint (same mechanism as native)
1. **Security**: Acceptable for internal tool with CSP, server-side validation, token rotation
1. **Conditional export direction**: `if (dart.library.io)` for native (exports nothing on web)
1. **Storage abstraction**: Platform-aware `AuthStorage` (not separate `TokenStorage`)
1. **CupertinoHttpClient on web**: No stub file needed - app code never references it directly,
   so conditional export that exports nothing on web is sufficient. Code that incorrectly
   tries to import `CupertinoHttpClient` directly will get a compile error, guiding
   developers to use `createPlatformClient()` instead.

## Risk Factors

1. **CORS**: If backend isn't configured for CORS, API calls will fail on web
   - Mitigation: Slice 2 verifies this early
1. **Cookies**: Backend auth uses session cookies which may have SameSite issues
1. **SSE on web**: EventSource should work but may have browser quirks
1. **Multi-tab state**: Web browsers can have multiple tabs with different auth states
   - Not addressed in this plan; accept as known limitation

## Review Notes

Plan reviewed by blacksmith and pathfinder agents (2026-01-07):

- Reordered slices to enable early verification
- Simplified token storage (3 files instead of 5)
- Fixed conditional export direction
- Added CORS verification step
- Added callback error handling
- Added browser history cleanup for security
- Added specific test matrix

Additional blacksmith review (2026-01-07) - CupertinoHttpClient handling:

- Investigated whether stub file is needed for `CupertinoHttpClient` on web
- Found: app code (`lib/`) never directly references `CupertinoHttpClient`
- Found: `createPlatformClient()` already handles web via existing stub pattern
- Decision: No stub file needed - conditional export that exports nothing on web
- Rationale: Simpler solution, compile error for misuse is better than runtime error
- Avoided: "stub" naming confusion (sounds like test mock, but isn't)
