# Fix: Stale Messages on Thread/Room Switch

## Problem

When switching threads/rooms, stale messages from the previous thread appeared.

## Root Cause

1. `activeRunNotifierProvider` didn't reset on thread change
2. No historical message fetching - messages lost on thread switch

## Solution

1. **Reset on thread change** - Listen to `threadSelectionProvider`, call `reset()`
   when leaving a selected thread
2. **Message caching** - `ThreadMessageCache` as single source of truth with
   backend fetch on miss
3. **Explicit room binding** - `HistoryPanel` receives `roomId` as parameter
   (eliminates timing bugs)

## Architecture

```text
Thread Selection
      │
      ▼
┌─────────────────────────────┐
│ threadMessageCacheProvider  │ ← Single source of truth
└──────────────┬──────────────┘
               │
     ┌─────────┴─────────┐
     │ Cache hit?        │
     └─────────┬─────────┘
           Yes │           No
               │            │
               ▼            ▼
       Return cached    api.getThreadMessages()
       (instant)        → cache → return
```

## Key Design Decisions

1. **`reset()` clears immediately, disposes async** - UI updates instantly,
   cleanup in background
2. **Listen to sealed `ThreadSelection`** - Type-safe `previous is ThreadSelected`
   vs nullable string checks
3. **Single cache provider** - Avoids dual source of truth between run state
   and historical messages
4. **Event replay via `processEvent()`** - Reuses existing logic for consistency
5. **In-flight request deduplication** - `_inFlightFetches` map prevents
   concurrent API calls for same thread

## Implementation Summary

| Component | Change |
|-----------|--------|
| `ActiveRunNotifier` | Listens to thread selection, resets on change |
| `ThreadMessageCache` | New provider: cache + fetch-on-miss |
| `allMessagesProvider` | Now `FutureProvider`, merges cached + streaming |
| `SoliplexApi` | Added `getThreadMessages()` with event replay |
| `HistoryPanel` | Explicit `roomId` parameter (not derived from provider) |
| `MessageList` | Handles `AsyncValue<List<ChatMessage>>` |

## Files Changed

**Core providers:**

- `lib/core/providers/active_run_notifier.dart` - thread listener, async reset
- `lib/core/providers/active_run_provider.dart` - `allMessagesProvider` as FutureProvider
- `lib/core/providers/thread_message_cache.dart` - new cache provider

**UI:**

- `lib/features/history/history_panel.dart` - explicit `roomId` parameter
- `lib/features/room/room_screen.dart` - passes `roomId` to HistoryPanel
- `lib/features/chat/widgets/message_list.dart` - AsyncValue handling

**Client:**

- `packages/soliplex_client/lib/src/api/soliplex_api.dart` - `getThreadMessages()`

## Acceptance Criteria

- [x] `reset()` is async with immediate state clear
- [x] State resets when leaving a selected thread
- [x] No reset on initial thread selection
- [x] Historical messages fetched from backend
- [x] Cache prevents redundant API calls
- [x] Messages deduplicated (cached + streaming)
- [x] Run completion updates cache
- [x] HistoryPanel shows correct room's threads
- [x] All tests pass (461)
- [x] Analyzer reports 0 issues
