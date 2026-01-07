# Fix: Stale Messages on Thread/Room Switch

## Problem

When user switches rooms or threads, `activeRunNotifierProvider` retains messages
from the previous thread, causing stale content to display.

## Root Cause

`activeRunNotifierProvider` doesn't listen to thread changes. The `allMessagesProvider`
merges historical messages (correctly keyed by thread) with active run messages
(not reset on thread change).

## Solution

Make `activeRunNotifierProvider` listen to `currentThreadIdProvider` and call
`reset()` when the thread changes. This enforces the domain invariant: **run state
is scoped to a thread**.

## Design Decisions (per blacksmith consultation)

1. **Fix `reset()` async bug first** - Current `reset()` doesn't await `dispose()`,
   creating potential race conditions
2. **Use `IdleState` on reset** - Thread switch is context change, not user
   cancellation (unlike `cancelRun()` which uses `CompletedState`)
3. **Clear state immediately, dispose in background** - UI clears instantly on
   thread switch; async disposal happens afterward to prevent race conditions
4. **Only reset when switching away from a thread** - `previous != null` check
   prevents unnecessary reset on initial thread selection

## Implementation Plan

### Slice 1: Make `reset()` async with immediate state clear

**Goal:** Fix existing bug where `reset()` doesn't await async disposal. Clear
state immediately so UI updates instantly, then await disposal.

**TDD Steps:**

1. Write test: `reset() clears state immediately and awaits disposal`
   - Start a run, call `reset()`, verify state is IdleState immediately
   - Verify disposal completes before reset() returns
   - Location: `test/core/providers/active_run_notifier_test.dart`

2. Write test: `rapid resets do not cause concurrent disposal issues`
   - Start a run
   - Call reset() multiple times in quick succession
   - Verify no exceptions, final state is idle
   - Location: `test/core/providers/active_run_notifier_test.dart`

3. Run tests → expect failure (current `reset()` is sync, doesn't await)

4. Implement:
   - Change `reset()` signature to `Future<void> reset() async`
   - Clear state immediately, then await disposal:

   ```dart
   Future<void> reset() async {
     final previousState = _internalState;
     _internalState = const IdleInternalState();
     state = const IdleState();  // UI clears immediately

     if (previousState is RunningInternalState) {
       await previousState.dispose();  // Cleanup completes before return
     }
   }
   ```

   - Location: `lib/core/providers/active_run_notifier.dart:244`

5. Run tests → expect pass

6. Run all existing tests → expect pass (no breaking changes)

**Files:**

- `lib/core/providers/active_run_notifier.dart` - change `reset()` signature
- `test/core/providers/active_run_notifier_test.dart` - add test

### Slice 2: Reset on thread change

**Goal:** Active run state resets when user switches away from a thread.

**TDD Steps:**

1. Write test: `resets state when switching from one thread to another`
   - Override `threadSelectionProvider` (which `currentThreadIdProvider` derives from)
   - Select thread A, start a run, verify messages exist
   - Select thread B
   - Verify state is `IdleState` with empty messages
   - Location: `test/core/providers/active_run_notifier_test.dart`

2. Write test: `does not reset when initially selecting a thread (null -> threadId)`
   - Start with no thread selected
   - Select thread A
   - Verify no reset occurred (or if it did, it was a no-op)
   - Location: `test/core/providers/active_run_notifier_test.dart`

3. Run tests → expect failure (no listener exists)

4. Implement:
   - Add import for `threads_provider.dart` in `active_run_notifier.dart`
   - Add `ref.listen()` in `build()` method:

   ```dart
   @override
   ActiveRunState build() {
     _agUiClient = ref.watch(agUiClientProvider);

     // Reset when switching away from a thread (run state is scoped to thread)
     ref.listen(currentThreadIdProvider, (previous, next) {
       if (previous != null) {
         reset();
       }
     });

     ref.onDispose(() {
       if (_internalState is RunningInternalState) {
         (_internalState as RunningInternalState).dispose();
       }
     });

     return const IdleState();
   }
   ```

   - Location: `lib/core/providers/active_run_notifier.dart:68-79`

5. Run tests → expect pass

6. Run all tests → expect pass

**Files:**

- `lib/core/providers/active_run_notifier.dart` - add import and listener
- `test/core/providers/active_run_notifier_test.dart` - add tests

**Test setup note:** Override `threadSelectionProvider` directly in `ProviderContainer`.
`currentThreadIdProvider` derives from it, so changing `threadSelectionProvider`
will trigger the listener.

### Slice 3: Verification

**Automated checks:**

1. Run analyzer: `mcp__dart__analyze_files` → must be 0 issues
2. Run all tests: `mcp__dart__run_tests` → must pass

**Manual verification:**

1. Start backend: `/start-backend`
2. Launch app on simulator/device
3. Test scenarios:
   - Go to Room A, send message, see response
   - Switch to Room B → verify no stale messages from Room A
   - If Room B has threads → verify correct thread's messages show
   - If Room B has no threads → verify empty state
   - Switch threads within same room → verify messages update correctly
   - Rapid thread switching → verify no crashes or stale state

## Acceptance Criteria

### Slice 1-2: Stale Message Prevention

- [x] `reset()` is async with immediate state clear, then awaited disposal
- [x] State resets to `IdleState` when leaving a selected thread (`previous is ThreadSelected`)
- [x] No reset on initial thread selection (`NoThreadSelected -> ThreadSelected`)
- [x] All existing tests pass
- [x] New tests for reset behavior pass
- [x] Analyzer reports 0 issues

### Slice 3a: API Method + Event Replay (COMPLETED)

- [x] `SoliplexApi.getThreadMessages()` fetches thread and replays events
- [x] Runs are sorted by timestamp before replay
- [x] Reuses `processEvent()` for consistency
- [x] All tests pass

### Slice 3b: Thread Message Cache Provider (COMPLETED)

- [x] `threadMessageCacheProvider` is single source of truth
- [x] Cache hit returns instantly, cache miss fetches from backend
- [x] `updateMessages()` updates cache on run completion
- [x] All tests pass

### Slice 3c: Integration (COMPLETED)

- [x] `allMessagesProvider` merges cached + streaming messages (no duplicates)
- [x] Run completion updates cache via `updateMessages()`
- [x] `threadMessagesProvider` updated to use cache (not removed - still used)
- [x] Messages survive app restart AND thread switches
- [x] All tests pass (459)
- [x] Analyzer reports 0 issues

---

## Implementation Log

### Slice 1: COMPLETED (commit c4119bf)

**Files changed:**

- `lib/core/providers/active_run_notifier.dart`
- `lib/features/chat/chat_panel.dart`
- `test/core/providers/active_run_notifier_test.dart`
- `test/helpers/test_helpers.dart`

**Implementation decisions (via blacksmith consultation):**

1. **Error handling in `reset()`** - Added try-catch around disposal to ensure
   fire-and-forget callers (like Riverpod listeners) are safe. Errors are logged
   with `debugPrint()` but not rethrown.

2. **Import consolidation** - Replaced `package:meta/meta.dart` with
   `package:flutter/foundation.dart` since foundation provides both `@immutable`
   and `debugPrint`.

3. **`_handleRetry` signature** - Changed to `Future<void>` to match `_handleCancel`
   for consistency. Blacksmith confirmed: both are "do an async thing when user
   clicks button" - the semantic difference is implementation detail, not contract.

4. **Test naming** - Renamed `rapid resets do not cause concurrent disposal issues`
   to `calling reset multiple times is idempotent` for precision.

5. **`unawaited()` for Slice 2 listener** - Blacksmith recommends using
   `unawaited(reset())` in the listener to make fire-and-forget intent explicit.

### Slice 2: COMPLETED (INCOMPLETE - needs Slice 3)

**Files changed:**

- `lib/core/providers/active_run_notifier.dart` - added listener
- `test/core/providers/active_run_notifier_test.dart` - added thread change tests

**Implementation decisions (via blacksmith consultation):**

1. **Listen to `threadSelectionProvider` directly** - Instead of `currentThreadIdProvider`
   which returns nullable `String?`, we listen to the sealed type directly. This:
   - Eliminates null checks (`previous != null` → `previous is ThreadSelected`)
   - Is self-documenting ("reset when leaving a selected thread")
   - Is type-safe and future-proof

2. **Use `unawaited(reset())`** - Makes fire-and-forget intent explicit since listener
   callbacks must return `void`.

3. **Use cascade syntax** - `ref..listen()..onDispose()` per analyzer recommendation.

4. **YAGNI on extra tests** - Blacksmith confirmed we don't need tests for edge cases
   like `NewThreadIntent → ThreadSelected` because those transitions are safe by
   design (no stale data to clear).

**Final implementation:**

```dart
ref
  // Reset when leaving a selected thread (run state is scoped to thread)
  ..listen(threadSelectionProvider, (previous, next) {
    if (previous is ThreadSelected) {
      unawaited(reset());
    }
  })
  ..onDispose(() { ... });
```

**Issue discovered during manual testing:**

The fix correctly clears stale messages but now ALL messages disappear when switching
threads. This is because:

1. `threadMessagesProvider(threadId)` always returns `[]` in AM3 (no message history)
2. `reset()` clears `runState.messages`
3. `allMessagesProvider` = `threadMessagesProvider` (empty) + `runState.messages` (empty) = nothing

The fix is technically correct (no stale messages) but the UX is broken (no messages
at all). **Slice 3 is required to cache messages per-thread.**

---

## Slice 3: Historical Messages + Memory Cache (REQUIRED)

### Problem Analysis

The original fix assumed `threadMessagesProvider` would provide historical messages,
but in AM3 it always returns `[]`. Investigation revealed:

1. **Backend DOES store messages** - Events are persisted in runs and available via
   `GET /api/v1/rooms/{room_id}/agui/{thread_id}` which returns runs with `events` array

2. **Client doesn't fetch them** - `SoliplexApi.getThread()` returns `ThreadInfo`
   (metadata only), ignoring the events in the response

### Backend API

Confirmed via curl:

```bash
# GET /api/v1/rooms/{room_id}/agui/{thread_id} returns:
{
  "room_id": "...",
  "thread_id": "...",
  "runs": {
    "run-id-1": {
      "created": "2026-01-07T02:07:05.412829",
      "events": [
        {"type": "TEXT_MESSAGE_START", "messageId": "..."},
        {"type": "TEXT_MESSAGE_CONTENT", "delta": "Hello"},
        {"type": "TEXT_MESSAGE_END", "messageId": "..."}
      ]
    }
  }
}
```

### Design Decision (via blacksmith review)

**Single source of truth: `threadMessageCacheProvider`**

The original plan had two disconnected data sources (`threadMessagesProvider` +
cache in `ActiveRunNotifier`) which would cause race conditions and duplicate
messages. Blacksmith recommended a unified approach:

1. **Single `threadMessageCacheProvider`** - StateNotifier that handles both
   caching and backend fetch
2. **Remove `threadMessagesProvider`** - Replaced by the cache provider
3. **Update cache on run completion** - Not on thread switch (prevents data loss)
4. **Reuse `processEvent()`** - For event replay consistency
5. **Sort runs by timestamp** - Runs are a Map (unordered), must sort before replay

**Why not cache in `ActiveRunNotifier`?**

- Violates SRP (notifier manages run lifecycle, not message history)
- Riverpod can rebuild Notifiers, losing in-memory cache
- Creates dual source of truth with `threadMessagesProvider`

### Architecture

```text
Thread Selection
      │
      ▼
┌─────────────────────────────┐
│ threadMessageCacheProvider  │ ← Single source of truth
│ (StateNotifier)             │
└──────────────┬──────────────┘
               │
     ┌─────────┴─────────┐
     │ Cache hit?        │
     └─────────┬─────────┘
           Yes │           No
               │            │
               ▼            ▼
┌───────────────────┐  ┌─────────────────┐
│ Return cached     │  │ api.getThread   │
│ (sync)            │  │ Messages()      │
└───────────────────┘  └────────┬────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ Store in cache  │
                       │ Return messages │
                       └─────────────────┘


Run Completion (onDone)
      │
      ▼
┌─────────────────────────────┐
│ threadMessageCacheProvider  │
│ .updateMessages(threadId,   │
│   allCurrentMessages)       │
└─────────────────────────────┘
```

### Implementation Plan

#### Slice 3a: API Method + Event Replay

**Goal:** Add `SoliplexApi.getThreadMessages()` that fetches and replays events.

**TDD Steps:**

1. Write test: `getThreadMessages returns messages reconstructed from events`
   - Mock API to return thread with run events
   - Verify ChatMessage list is correctly reconstructed
   - Verify runs are processed in chronological order
   - Location: `packages/soliplex_client/test/api/soliplex_api_test.dart`

2. Run tests → expect failure

3. Implement in `soliplex_client`:

   ```dart
   // In SoliplexApi
   Future<List<ChatMessage>> getThreadMessages(
     String roomId,
     String threadId, {
     CancelToken? cancelToken,
   }) async {
     final response = await _transport.request<Map<String, dynamic>>(
       'GET',
       _urlBuilder.build(pathSegments: ['rooms', roomId, 'agui', threadId]),
       cancelToken: cancelToken,
     );

     final runs = response['runs'] as Map<String, dynamic>? ?? {};
     return _extractMessagesFromRuns(runs);
   }

   /// Extracts messages from runs by replaying events in chronological order.
   List<ChatMessage> _extractMessagesFromRuns(Map<String, dynamic> runs) {
     // Sort runs by created timestamp
     final sortedRuns = runs.entries.toList()
       ..sort((a, b) {
         final aCreated = a.value['created'] as String? ?? '';
         final bCreated = b.value['created'] as String? ?? '';
         return aCreated.compareTo(bCreated);
       });

     // Replay events using existing processEvent() logic
     var conversation = Conversation.empty();
     var streaming = const NotStreaming();

     for (final entry in sortedRuns) {
       final events = (entry.value['events'] as List<dynamic>?) ?? [];
       for (final eventJson in events) {
         final event = _parseEvent(eventJson as Map<String, dynamic>);
         if (event != null) {
           final result = processEvent(conversation, streaming, event);
           conversation = result.conversation;
           streaming = result.streaming;
         }
       }
     }

     return conversation.messages;
   }
   ```

4. Run tests → expect pass

**Files:**

- `packages/soliplex_client/lib/src/api/soliplex_api.dart` - add `getThreadMessages`
- `packages/soliplex_client/test/api/soliplex_api_test.dart` - add tests

#### Slice 3b: Thread Message Cache Provider

**Goal:** Single source of truth for thread messages with cache + fetch.

**TDD Steps:**

1. Write test: `getMessages returns cached messages on cache hit`
   - Pre-populate cache
   - Call `getMessages(roomId, threadId)`
   - Verify no API call made
   - Location: `test/core/providers/thread_message_cache_test.dart`

2. Write test: `getMessages fetches and caches on cache miss`
   - Empty cache
   - Call `getMessages(roomId, threadId)`
   - Verify API called, result cached
   - Location: `test/core/providers/thread_message_cache_test.dart`

3. Write test: `updateMessages updates cache for thread`
   - Call `updateMessages(threadId, messages)`
   - Verify cache updated
   - Location: `test/core/providers/thread_message_cache_test.dart`

4. Run tests → expect failure

5. Implement:

   ```dart
   // lib/core/providers/thread_message_cache.dart

   /// Cache state: threadId -> messages
   typedef ThreadMessageCacheState = Map<String, List<ChatMessage>>;

   /// Provides cached thread messages with backend fetch on miss.
   class ThreadMessageCache extends StateNotifier<ThreadMessageCacheState> {
     ThreadMessageCache(this._ref) : super({});

     final Ref _ref;

     /// Get messages for a thread (from cache or backend).
     Future<List<ChatMessage>> getMessages(
       String roomId,
       String threadId,
     ) async {
       // Cache hit
       if (state.containsKey(threadId)) {
         return state[threadId]!;
       }

       // Cache miss - fetch from backend
       final api = _ref.read(apiProvider);
       final messages = await api.getThreadMessages(roomId, threadId);

       // Store in cache
       state = {...state, threadId: messages};
       return messages;
     }

     /// Update cached messages for a thread (called on run completion).
     void updateMessages(String threadId, List<ChatMessage> messages) {
       state = {...state, threadId: messages};
     }

     /// Clear cache for a thread (called on thread deletion).
     void clearThread(String threadId) {
       state = Map.from(state)..remove(threadId);
     }

     /// Clear all cached messages (called on logout).
     void clearAll() {
       state = {};
     }
   }

   final threadMessageCacheProvider =
       StateNotifierProvider<ThreadMessageCache, ThreadMessageCacheState>(
     (ref) => ThreadMessageCache(ref),
   );
   ```

6. Run tests → expect pass

**Files:**

- `lib/core/providers/thread_message_cache.dart` - new provider
- `test/core/providers/thread_message_cache_test.dart` - tests

#### Slice 3c: Integration + Remove Old Provider

**Goal:** Wire up cache provider, update `allMessagesProvider`, update run completion.

**TDD Steps:**

1. Write test: `allMessagesProvider returns cached + streaming messages`
   - Set up cache with historical messages
   - Start a run with new messages
   - Verify merged result without duplicates
   - Location: `test/core/providers/active_run_provider_test.dart`

2. Write test: `run completion updates cache`
   - Start a run, complete it
   - Verify cache updated with all messages
   - Location: `test/core/providers/active_run_notifier_test.dart`

3. Run tests → expect failure

4. Implement:

   ```dart
   // Update allMessagesProvider in active_run_provider.dart
   final allMessagesProvider = Provider<List<ChatMessage>>((ref) {
     final thread = ref.watch(currentThreadProvider);
     if (thread == null) return [];

     final cache = ref.watch(threadMessageCacheProvider);
     final cached = cache[thread.id] ?? [];
     final runState = ref.watch(activeRunNotifierProvider);

     // Merge cached + run messages, deduplicating by ID
     return _mergeMessages(cached, runState.messages);
   });

   List<ChatMessage> _mergeMessages(
     List<ChatMessage> cached,
     List<ChatMessage> running,
   ) {
     final seenIds = <String>{};
     final result = <ChatMessage>[];

     // Add cached first
     for (final msg in cached) {
       if (seenIds.add(msg.id)) {
         result.add(msg);
       }
     }

     // Add running (may include new messages not yet cached)
     for (final msg in running) {
       if (seenIds.add(msg.id)) {
         result.add(msg);
       }
     }

     return result;
   }
   ```

   ```dart
   // In ActiveRunNotifier, update run completion handler
   void _onRunComplete() {
     final threadId = _currentThreadId;
     if (threadId != null) {
       ref.read(threadMessageCacheProvider.notifier)
           .updateMessages(threadId, state.messages);
     }
   }
   ```

5. Remove `threadMessagesProvider` (now unused)

6. Run tests → expect pass

7. Run all tests → expect pass

**Files:**

- `lib/core/providers/active_run_provider.dart` - update `allMessagesProvider`, remove `threadMessagesProvider`
- `lib/core/providers/active_run_notifier.dart` - call cache on completion
- `test/core/providers/active_run_provider_test.dart` - update tests

### Deferred (YAGNI)

| Item | Rationale |
|------|-----------|
| Cache eviction policy / size limits | Measure memory impact first |
| Thread deletion auto-cleanup | Thread deletion not implemented |
| Local persistence (SQLite) | Backend is source of truth |
| Optimistic cache invalidation | Simple refetch on invalidate works |

---

## Implementation Log (continued)

### Slice 3a: COMPLETED

**Files changed:**

- `packages/soliplex_client/lib/src/api/soliplex_api.dart` - added `getThreadMessages()`
- `packages/soliplex_client/test/api/soliplex_api_test.dart` - added 9 tests

**Implementation:**

Added `getThreadMessages(roomId, threadId)` method to `SoliplexApi`:

1. Fetches thread data from `GET /api/v1/rooms/{roomId}/agui/{threadId}`
2. Extracts runs from response (`runs` field)
3. Sorts runs by `created` timestamp (oldest first) using `_sortRunsByCreationTime()`
4. Replays events through `processEvent()` using `EventDecoder.decodeJson()`
5. Returns `List<ChatMessage>` from reconstructed `Conversation`

**Tests (9 passing):**

- `returns messages reconstructed from events` - basic event replay
- `processes runs in chronological order` - timestamp sorting
- `returns empty list when no runs` - empty state
- `returns empty list when runs have no events` - empty events
- `handles null runs gracefully` - null safety
- `validates non-empty roomId` - input validation
- `validates non-empty threadId` - input validation
- `uses correct URL` - URL construction
- `supports cancellation` - cancellation token

### Slice 3b: COMPLETED

**Files created:**

- `lib/core/providers/thread_message_cache.dart` - new cache provider
- `test/core/providers/thread_message_cache_test.dart` - 10 tests

**Implementation:**

Created `ThreadMessageCache` as a Riverpod `Notifier<Map<String, List<ChatMessage>>>`:

1. `getMessages(roomId, threadId)` - returns cached messages on hit, fetches via
   `api.getThreadMessages()` on miss, caches result
2. `updateMessages(threadId, messages)` - updates cache entry (for run completion)
3. `clearThread(threadId)` - removes cache entry (for thread deletion)
4. `clearAll()` - clears entire cache (for logout)

**Tests (10 passing):**

- `getMessages` group (4 tests): cache hit, cache miss, subsequent calls, separate threads
- `updateMessages` group (3 tests): update, overwrite, isolation
- `clearThread` group (2 tests): removal, isolation
- `clearAll` group (1 test): full clear

### Slice 3c: COMPLETED

**Files changed:**

- `lib/core/providers/active_run_provider.dart` - updated `threadMessagesProvider` and
  `allMessagesProvider`
- `lib/core/providers/active_run_notifier.dart` - added cache update on run completion
- `test/features/chat/chat_panel_test.dart` - added provider override for cache

**Implementation:**

1. **Updated `threadMessagesProvider`** to use `ThreadMessageCache`:
   - Changed from direct API call to `cache.getMessages(roomId, threadId)`
   - Returns cached messages on hit, fetches on miss

2. **Updated `allMessagesProvider`** with deduplication:
   - Added `_mergeMessages()` helper that deduplicates by message ID
   - Merges cached (historical) + running (streaming) messages
   - Order: cached first, then new running messages not yet cached

3. **Added `_updateCacheOnCompletion()`** to `ActiveRunNotifier`:
   - Called from all completion paths: `_mapResultToState()`, `onDone`, `onError`,
     `cancelRun`, and catch blocks
   - Updates cache with current messages on run completion

4. **Fixed failing test** `input enabled when room selected`:
   - Test now overrides `threadMessagesProvider` to return empty list
   - Prevents API call during widget test

**Tests:**

All 459 tests pass. Analyzer reports 0 issues.

### Blacksmith Review Fixes: COMPLETED

**Issues addressed:**

1. **Race condition in cache fetch** (Major) - Added `_inFlightFetches` map to
   deduplicate concurrent requests for the same thread. Concurrent callers now
   share the same future via `??=` operator.

2. **`clearThread()` type annotation** (Minor) - Changed from verbose
   `Map<String, List<ChatMessage>>.from(state)` to spread syntax `{...state}`.

3. **No error handling for malformed events** (Minor) - Added try-catch around
   event replay in `_extractMessagesFromRuns()`. Malformed events are skipped
   with debug logging (via assert) rather than failing the entire history fetch.

4. **No integration tests for `threadMessagesProvider`** (Minor) - Added 3
   integration tests verifying cache usage via `threadMessagesProvider`.

**New tests added (4):**

- `concurrent fetches share single API request` - verifies race condition fix
- `threadMessagesProvider uses cache on hit (no API call)` - integration test
- `threadMessagesProvider fetches from API on cache miss` - integration test
- `threadMessagesProvider returns empty list when no room selected`

**Tests:**

All 463 tests pass. Analyzer reports 0 issues.
