/// Centralized provider declarations for server-scoped panel state.
///
/// All panel providers are declared here and MUST watch
/// currentServerFromAppStateProvider.
/// This ensures automatic state reset when switching servers.
///
/// For per-room state, use the family-based providers:
/// - [roomCanvasProvider] - Canvas state keyed by ServerRoomKey
/// - [roomContextPaneProvider] - Context pane state keyed by ServerRoomKey
///
/// For UI convenience, use the active providers:
/// - [activeServerRoomKeyProvider] - Current ServerRoomKey
/// - [activeCanvasProvider] - Canvas state for current room
/// - [activeContextPaneProvider] - Context pane state for current room
///
/// When adding a new panel:
/// 1. Create a notifier that extends ServerScopedNotifier
/// 2. Add the provider declaration here
/// 3. Make sure it watches [currentServerFromAppStateProvider]
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rxdart/rxdart.dart';
import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/core/network/connection_registry.dart';
import 'package:soliplex/core/network/server_room_key.dart';
import 'package:soliplex/core/providers/app_providers.dart';
import 'package:soliplex/core/services/activity_status_service.dart';
import 'package:soliplex/core/services/canvas_service.dart';
import 'package:soliplex/core/services/completions_session_manager.dart';
import 'package:soliplex/core/services/context_pane_service.dart';
import 'package:soliplex/core/services/rooms_service.dart'
    show selectedRoomProvider;
import 'package:soliplex/core/services/tool_execution_service.dart';

// =============================================================================
// ACTIVE SERVER+ROOM KEY
// =============================================================================

/// Provider for the current server+room key.
///
/// Returns null if no server or room is selected.
/// Use this to derive active state from family providers.
final activeServerRoomKeyProvider = Provider<ServerRoomKey?>((ref) {
  final server = ref.watch(currentServerFromAppStateProvider);
  final roomId = ref.watch(selectedRoomProvider);

  if (server == null || roomId == null) return null;
  return ServerRoomKey(serverId: server.id, roomId: roomId);
});

// =============================================================================
// CANVAS PANEL
// =============================================================================

/// Per-room canvas state provider (family).
///
/// Keyed by ServerRoomKey - maintains separate canvas state per room.
/// Use [activeCanvasProvider] for UI convenience.
final StateNotifierProviderFamily<CanvasNotifier, CanvasState, ServerRoomKey>
roomCanvasProvider =
    StateNotifierProvider.family<CanvasNotifier, CanvasState, ServerRoomKey>(
      (ref, key) => CanvasNotifier(serverId: key.serverId, roomId: key.roomId),
    );

/// Active canvas state for current room.
///
/// Convenience provider that derives from [roomCanvasProvider] using
/// activeServerRoomKeyProvider. Returns empty state if no room selected.
final activeCanvasProvider = Provider<CanvasState>((ref) {
  final key = ref.watch(activeServerRoomKeyProvider);
  if (key == null) return const CanvasState();
  return ref.watch(roomCanvasProvider(key));
});

/// Active canvas notifier for current room.
///
/// Returns the notifier for the current room, or null if no room selected.
/// Use this to modify canvas state.
final activeCanvasNotifierProvider = Provider<CanvasNotifier?>((ref) {
  final key = ref.watch(activeServerRoomKeyProvider);
  if (key == null) return null;
  return ref.read(roomCanvasProvider(key).notifier);
});

/// Legacy provider for canvas state (server-scoped only).
///
/// DEPRECATED: Prefer [roomCanvasProvider] for per-room state.
/// Watches [currentServerFromAppStateProvider] - canvas clears when server
/// changes.
final canvasProvider = StateNotifierProvider<CanvasNotifier, CanvasState>((
  ref,
) {
  final server = ref.watch(currentServerFromAppStateProvider);
  return CanvasNotifier(serverId: server?.id);
});

// =============================================================================
// CONTEXT PANE
// =============================================================================

/// Per-room context pane state provider (family).
///
/// Keyed by ServerRoomKey - maintains separate context pane per room.
/// Use [activeContextPaneProvider] for UI convenience.
final StateNotifierProviderFamily<
  ContextPaneNotifier,
  ContextPaneState,
  ServerRoomKey
>
roomContextPaneProvider =
    StateNotifierProvider.family<
      ContextPaneNotifier,
      ContextPaneState,
      ServerRoomKey
    >(
      (ref, key) =>
          ContextPaneNotifier(serverId: key.serverId, roomId: key.roomId),
    );

/// Active context pane state for current room.
///
/// Convenience provider that derives from [roomContextPaneProvider] using
/// activeServerRoomKeyProvider. Returns empty state if no room selected.
final activeContextPaneProvider = Provider<ContextPaneState>((ref) {
  final key = ref.watch(activeServerRoomKeyProvider);
  if (key == null) return const ContextPaneState();
  return ref.watch(roomContextPaneProvider(key));
});

/// Active context pane notifier for current room.
///
/// Returns the notifier for the current room, or null if no room selected.
/// Use this to modify context pane state.
final activeContextPaneNotifierProvider = Provider<ContextPaneNotifier?>((ref) {
  final key = ref.watch(activeServerRoomKeyProvider);
  if (key == null) return null;
  return ref.read(roomContextPaneProvider(key).notifier);
});

/// Legacy provider for context pane state (server-scoped only).
///
/// DEPRECATED: Prefer [roomContextPaneProvider] for per-room state.
/// Watches [currentServerFromAppStateProvider] - context pane clears when
/// server changes.
final contextPaneProvider =
    StateNotifierProvider<ContextPaneNotifier, ContextPaneState>((ref) {
      final server = ref.watch(currentServerFromAppStateProvider);
      return ContextPaneNotifier(serverId: server?.id);
    });

// =============================================================================
// ACTIVITY STATUS
// =============================================================================

/// Per-room activity status state provider (family).
///
/// Keyed by ServerRoomKey - maintains separate activity status per room.
/// This prevents timer race conditions: each room's notifier is independent,
/// and timers are properly scoped to the room lifecycle.
///
/// Use [activeActivityStatusProvider] for UI convenience.
final StateNotifierProviderFamily<
  ActivityStatusNotifier,
  ActivityStatusState,
  ServerRoomKey
>
roomActivityStatusProvider =
    StateNotifierProvider.family<
      ActivityStatusNotifier,
      ActivityStatusState,
      ServerRoomKey
    >(
      (ref, key) => ActivityStatusNotifier(
        config: ref.watch(activityStatusConfigProvider),
        serverId: key.serverId,
        roomId: key.roomId,
      ),
    );

/// Active activity status state for current room.
///
/// Convenience provider that derives from [roomActivityStatusProvider] using
/// activeServerRoomKeyProvider. Returns empty state if no room selected.
final activeActivityStatusProvider = Provider<ActivityStatusState>((ref) {
  final key = ref.watch(activeServerRoomKeyProvider);
  if (key == null) return const ActivityStatusState();
  return ref.watch(roomActivityStatusProvider(key));
});

/// Active activity status notifier for current room.
///
/// Returns the notifier for the current room, or null if no room selected.
/// Use this to modify activity status state.
final activeActivityStatusNotifierProvider = Provider<ActivityStatusNotifier?>((
  ref,
) {
  final key = ref.watch(activeServerRoomKeyProvider);
  if (key == null) return null;
  return ref.read(roomActivityStatusProvider(key).notifier);
});

// =============================================================================
// MESSAGE STREAM (Bridge)
// =============================================================================

/// Per-room message stream provider (family).
///
/// Subscribes to the RoomSession's message stream.
/// This ensures we get updates even if ConnectionManager doesn't notify.
final StreamProviderFamily<List<ChatMessage>, ServerRoomKey>
roomMessageStreamProvider =
    StreamProvider.family<List<ChatMessage>, ServerRoomKey>((ref, key) {
      final registry = ref.watch(connectionRegistryProvider);
      // We use getSession to ensure it exists and we're subscribed
      final session = registry.getSession(key);
      return session.messageStream.startWith(session.messages);
    });

/// Active message stream for the current room (AG-UI only).
///
/// UI watches this to get real-time message updates.
/// Returns an empty list if no room is selected.
/// Uses startWith to ensure current state is available immediately.
///
/// DEPRECATED: Prefer [unifiedMessageStreamProvider] which handles both modes.
final activeMessageStreamProvider = Provider<AsyncValue<List<ChatMessage>>>((
  ref,
) {
  final key = ref.watch(activeServerRoomKeyProvider);
  if (key == null) return const AsyncData([]);

  // We use roomMessageStreamProvider to ensure per-room caching/scoping
  return ref.watch(roomMessageStreamProvider(key));
});

/// Unified message stream provider that returns messages from either
/// AG-UI rooms or completions endpoints based on current mode.
///
/// This is the primary provider UI should use for displaying messages.
/// It automatically switches between:
/// - AG-UI mode: Messages from [roomMessageStreamProvider] for selected room
/// - Completions mode: Messages from [completionsMessageStreamProvider]
final unifiedMessageStreamProvider = Provider<AsyncValue<List<ChatMessage>>>((
  ref,
) {
  final isCompletionsMode = ref.watch(isCompletionsModeProvider);

  if (isCompletionsMode) {
    // Completions mode - use completions session messages
    return ref.watch(completionsMessageStreamProvider);
  } else {
    // AG-UI mode - use room session messages
    final key = ref.watch(activeServerRoomKeyProvider);
    if (key == null) return const AsyncData([]);
    return ref.watch(roomMessageStreamProvider(key));
  }
});

// =============================================================================
// TOOL EXECUTION
// =============================================================================

/// Per-room tool execution state provider (family).
///
/// Keyed by ServerRoomKey - maintains separate tool execution state per room.
/// This prevents cross-contamination: switching rooms won't show stale tool
/// indicators from another room.
///
/// Use [activeToolExecutionProvider] for UI convenience.
final StateNotifierProviderFamily<
  ToolExecutionNotifier,
  ToolExecutionState,
  ServerRoomKey
>
roomToolExecutionProvider =
    StateNotifierProvider.family<
      ToolExecutionNotifier,
      ToolExecutionState,
      ServerRoomKey
    >(
      (ref, key) =>
          ToolExecutionNotifier(serverId: key.serverId, roomId: key.roomId),
    );

/// Active tool execution state for current room.
///
/// Convenience provider that derives from [roomToolExecutionProvider] using
/// activeServerRoomKeyProvider. Returns empty state if no room selected.
final activeToolExecutionProvider = Provider<ToolExecutionState>((ref) {
  final key = ref.watch(activeServerRoomKeyProvider);
  if (key == null) return const ToolExecutionState();
  return ref.watch(roomToolExecutionProvider(key));
});

/// Active tool execution notifier for current room.
///
/// Returns the notifier for the current room, or null if no room selected.
/// Use this to modify tool execution state.
final activeToolExecutionNotifierProvider = Provider<ToolExecutionNotifier?>((
  ref,
) {
  final key = ref.watch(activeServerRoomKeyProvider);
  if (key == null) return null;
  return ref.read(roomToolExecutionProvider(key).notifier);
});
