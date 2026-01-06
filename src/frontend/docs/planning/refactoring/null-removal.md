# Null Removal Opportunities

Identified nullable types that could be replaced with non-nullable alternatives.

## Review Status

Reviewed by blacksmith and sentinel agents. Most initially identified candidates
should remain nullable - they represent semantically meaningful absence.

## Actionable Items

### `http_event_group.dart` - Force Unwraps (Medium Priority)

**File:** `lib/features/inspector/models/http_event_group.dart`

**Current:** 5 nullable event fields with force unwraps (`!`)

```dart
class HttpEventGroup {
  final HttpRequestEvent? request;
  final HttpResponseEvent? response;
  final HttpErrorEvent? error;
  final HttpStreamStartEvent? streamStart;
  final HttpStreamEndEvent? streamEnd;

  String get method {
    if (request != null) return request!.method;  // force unwrap
    // ...
  }

  String get statusDescription {
    return switch (status) {
      HttpEventStatus.success => 'status ${response!.statusCode}',  // unwrap
      // ...
    };
  }
}
```

**Fix - Pattern Guards:**

```dart
String get statusDescription {
  return switch (status) {
    HttpEventStatus.success when response case HttpResponseEvent(:final statusCode)
      => 'success, status $statusCode',
    HttpEventStatus.clientError when response case HttpResponseEvent(:final statusCode)
      => 'client error, status $statusCode',
    _ => '${status.name}',
  };
}
```

Pattern guards eliminate force unwraps while keeping the nullable fields (which
are semantically correct - events arrive asynchronously and may not all be present).

---

## Keep As-Is (Semantically Correct)

| File | Field | Reason |
|------|-------|--------|
| `auth_flow.dart:10` | `refreshToken` | Optional per OAuth 2.0 spec (RFC 6749 Section 4.1.4). Null vs empty string distinction needed for debugging auth issues. |
| `auth_state.dart:37` | `idToken` | Required for OIDC logout |
| `loading_indicator.dart:7` | `message` | Null means "show no message" (spinner only). Default would change behavior - always showing text. |
| `async_value_handler.dart:46-47` | `onRetry`, `loading` | Callbacks legitimately optional |
| `shell_config.dart` | `title`, `drawer`, `fab` | UI configuration truly optional |
| `error_display.dart` | `onRetry` | Not all errors support retry |

---

## Review Notes

### Auth Tokens (Rejected)

**Original proposal:** Default `refreshToken` and `idToken` to empty string.

**Why rejected (Sentinel - CAT II):**

1. Conflates "IdP didn't provide token" with "token is empty string"
2. Masks errors instead of failing fast
3. Empty string could reach security-sensitive code paths (e.g., `endSession()`)
4. Loses debugging clarity - can't distinguish missing vs corrupted tokens

The current nullable design provides better security properties. The localized
fallback in `auth_notifier.dart:200` (`result.refreshToken ?? ''`) is appropriate
for storage; making the model non-nullable propagates the lossy conversion everywhere.

### LoadingIndicator (Rejected)

**Original proposal:** Default `message` to `'Loading'`.

**Why rejected (Blacksmith):**

This changes behavior, not just null-safety:

- Current: `LoadingIndicator()` shows spinner only
- Proposed: `LoadingIndicator()` shows spinner + "Loading" text

The null is semantically meaningful - it distinguishes "show no message" from
"show default message". Callers who want "Loading" displayed would pass it explicitly.

### HttpEventGroup Sealed Class (Rejected)

**Original proposal:** Option B with `EventSlot<T>` sealed class.

**Why rejected (Blacksmith):**

Over-engineering for a binary present/absent distinction. The sealed class is
isomorphic to `T?` - same two cases, more boilerplate. Pattern guards (Option A)
are the right fix: safe, expressive, no added abstraction.

---

## Patterns to Follow

Good examples already in codebase:

- `room.dart:10` - `description = ''`
- `thread_info.dart:12-15` - `initialRunId = ''`, `name = ''`
- `run_info.dart:64-67` - `label = ''`, `metadata = const {}`
- `conversation.dart:134-136` - `messages = const []`, `status = const Idle()`

These work because empty string/collection is a valid domain value, not a sentinel
for "missing". Apply this pattern only when the empty value is meaningful in the domain.
