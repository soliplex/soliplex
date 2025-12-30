# MobileAuthProvider Code Review Fixes

Fixes identified by blacksmith review of Commit 6 (Mobile Auth Provider).

## Issues

### Major #1: Config Cache Silent Failure

**Problem:** `_configCache` is in-memory only. After app restart, `getValidToken()` silently fails to refresh tokens (returns `RefreshFailed` instead of attempting refresh) and `getCurrentUser()` throws because no config is found.

**Decision:** Option 2 - Require SsoConfig as parameter

**Fix:**
1. Update `AuthProvider` interface to require `SsoConfig` parameter for `getValidToken()` and `getCurrentUser()`
2. Update `MobileAuthProvider` implementation
3. Update all tests

### Major #2: Logout Interface Contract Violation

**Problem:** `AuthProvider.logout()` interface documents it throws `AuthErrorNetwork`/`AuthErrorServer` on failure, but implementation silently swallows all exceptions.

**Decision:** Option B - Change contract to match implementation

**Fix:**
1. Update `AuthProvider.logout()` interface doc to say it never throws
2. Add `debugPrint` logging for failed end-session in implementation

### Minor #3: Fragile Cast After Pattern Match

**Problem:** Line 141 uses `(result as TokenFound).token` after pattern matching, which is fragile.

**Decision:** Use switch expression

**Fix:** Replace if-check + cast with exhaustive switch expression:
```dart
final token = switch (result) {
  TokenFound(:final token) => token,
  TokenNotFound() => throw const AuthErrorNotAuthenticated(),
};
```

### Minor #4: Test Setup Duplication

**Problem:** "Login to cache config" pattern repeated ~10 times in tests.

**Decision:** Option B - Extract `loginToCache()` helper

**Fix:** Add helper function that handles the repeated login-to-cache pattern:
```dart
Future<void> loginToCache(SsoConfig config) async {
  when(() => mockAppAuth.authorizeAndExchangeCode(any()))
      .thenAnswer((_) async => createAuthResponse());
  when(() => mockStorage.write(any(), any())).thenAnswer((_) async {});
  await provider.login('server1', config);
}
```

### Minor #5: Missing Test for Config Eviction

**Problem:** No test verifies that `logout()` removes config from cache.

**Decision:** Add behavioral tests that observe config eviction

**Fix:** Add two tests:
1. Test `getCurrentUser` fails with `AuthErrorConfiguration` after logout
2. Test token refresh returns `RefreshFailed` after logout (never attempts refresh)

## Status

- [ ] Major #1: Config cache - Require SsoConfig parameter
- [ ] Major #2: Logout contract - Update docs, add logging
- [ ] Minor #3: Fragile cast - Use switch expression
- [ ] Minor #4: Test duplication - Extract `loginToCache()` helper
- [ ] Minor #5: Config eviction test - Add two behavioral tests
