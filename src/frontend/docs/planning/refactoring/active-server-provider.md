# Refactor: Extract Active Server Provider

## Summary

Extract `activeServerProvider` from `appStateProvider` to fix Dependency Inversion
violation in `urlBuilderProvider`.

## Problem

`urlBuilderProvider` (low-level infrastructure) directly watches `appStateProvider`
(high-level auth UI state):

```dart
// api_provider.dart:71-85
final urlBuilderProvider = Provider<UrlBuilder>((ref) {
  final appState = ref.watch(appStateProvider);  // ← Problem
  final config = ref.watch(configProvider);

  final baseUrl = switch (appState) {
    AppStateNoServer() => config.baseUrl,
    AppStateProbing(:final serverId) => serverId,
    AppStateNeedsAuth(:final serverId) => serverId,
    AppStateAuthenticating(:final serverId) => serverId,
    AppStateReady(:final serverId) => serverId,
    AppStateError(:final serverId) => serverId ?? config.baseUrl,
  };

  return UrlBuilder('$baseUrl/api/v1');
});
```

### Issues

1. **DIP Violation**: Low-level URL building depends on high-level auth state.
   The URL builder only needs a server URL string, not the entire auth lifecycle.

2. **Unnecessary Rebuilds**: Any auth state change (e.g., user info update,
   auth error) triggers URL builder rebuild even when server URL unchanged.

3. **Feature Envy**: URL builder reaches into auth state to extract one field.
   This knowledge should live elsewhere.

4. **Tight Coupling**: Infrastructure providers are coupled to auth UI concerns.

## Solution

Introduce `activeServerProvider` that provides just the server URL:

```dart
/// Provider for the active server URL.
///
/// Extracts server URL from app state, defaulting to config when no server
/// is configured. This provider exists to decouple infrastructure (URL building,
/// HTTP transport) from auth UI state.
///
/// **Lifecycle**: Updates only when the server URL actually changes, not on
/// every auth state transition.
final activeServerProvider = Provider<String>((ref) {
  final appState = ref.watch(appStateProvider);
  final config = ref.watch(configProvider);

  return switch (appState) {
    AppStateNoServer() => config.baseUrl,
    AppStateProbing(:final serverId) => serverId,
    AppStateNeedsAuth(:final serverId) => serverId,
    AppStateAuthenticating(:final serverId) => serverId,
    AppStateReady(:final serverId) => serverId,
    AppStateError(:final serverId) => serverId ?? config.baseUrl,
  };
});

/// Provider for the URL builder.
///
/// Creates a [UrlBuilder] configured with the active server URL from
/// [activeServerProvider].
final urlBuilderProvider = Provider<UrlBuilder>((ref) {
  final baseUrl = ref.watch(activeServerProvider);
  return UrlBuilder('$baseUrl/api/v1');
});
```

## Benefits

1. **DIP Compliance**: URL builder depends on abstraction (server URL string)
   not concrete auth state implementation.

2. **Selective Rebuilds**: Riverpod dedupes provider values. If `serverId`
   hasn't changed between auth state transitions, downstream providers don't
   rebuild.

3. **Clear Responsibility**: `activeServerProvider` owns the "which server"
   question. Other providers ask it, don't figure it out themselves.

4. **Testability**: Easy to override `activeServerProvider` in tests without
   setting up full auth state.

## Implementation Steps

1. Add `activeServerProvider` to `lib/core/providers/api_provider.dart`
2. Update `urlBuilderProvider` to watch `activeServerProvider` instead of `appStateProvider`
3. Update tests that override `urlBuilderProvider` to instead override `activeServerProvider`
4. Run tests to verify no regressions

## Files to Modify

- `lib/core/providers/api_provider.dart` - Add provider, update urlBuilderProvider
- Tests that mock URL building behavior

## Related

- `lib/core/providers/auth_providers.dart` - AppStateNotifier (unchanged)
- `lib/core/state/app_state.dart` - AppState sealed class (unchanged)
