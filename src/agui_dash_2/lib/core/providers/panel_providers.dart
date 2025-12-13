/// Centralized provider declarations for server-scoped panel state.
///
/// All panel providers are declared here and MUST watch [currentServerFromAppStateProvider].
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
/// 1. Create a notifier that extends [ServerScopedNotifier]
/// 2. Add the provider declaration here
/// 3. Make sure it watches [currentServerFromAppStateProvider]
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../network/server_room_key.dart';
import '../services/activity_status_service.dart';
import '../services/canvas_service.dart';
import '../services/context_pane_service.dart';
import '../services/rooms_service.dart' show selectedRoomProvider;
import 'app_providers.dart';

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
/// Keyed by [ServerRoomKey] - maintains separate canvas state per room.
/// Use [activeCanvasProvider] for UI convenience.
final roomCanvasProvider =
    StateNotifierProvider.family<CanvasNotifier, CanvasState, ServerRoomKey>(
  (ref, key) => CanvasNotifier(serverId: key.serverId, roomId: key.roomId),
);

/// Active canvas state for current room.
///
/// Convenience provider that derives from [roomCanvasProvider] using
/// [activeServerRoomKeyProvider]. Returns empty state if no room selected.
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
/// Watches [currentServerFromAppStateProvider] - canvas clears when server changes.
final canvasProvider = StateNotifierProvider<CanvasNotifier, CanvasState>((ref) {
  final server = ref.watch(currentServerFromAppStateProvider);
  return CanvasNotifier(serverId: server?.id);
});

// =============================================================================
// CONTEXT PANE
// =============================================================================

/// Per-room context pane state provider (family).
///
/// Keyed by [ServerRoomKey] - maintains separate context pane per room.
/// Use [activeContextPaneProvider] for UI convenience.
final roomContextPaneProvider =
    StateNotifierProvider.family<ContextPaneNotifier, ContextPaneState, ServerRoomKey>(
  (ref, key) => ContextPaneNotifier(serverId: key.serverId, roomId: key.roomId),
);

/// Active context pane state for current room.
///
/// Convenience provider that derives from [roomContextPaneProvider] using
/// [activeServerRoomKeyProvider]. Returns empty state if no room selected.
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
/// Watches [currentServerFromAppStateProvider] - context pane clears when server changes.
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
/// Keyed by [ServerRoomKey] - maintains separate activity status per room.
/// This prevents timer race conditions: each room's notifier is independent,
/// and timers are properly scoped to the room lifecycle.
///
/// Use [activeActivityStatusProvider] for UI convenience.
final roomActivityStatusProvider = StateNotifierProvider.family<
    ActivityStatusNotifier, ActivityStatusState, ServerRoomKey>(
  (ref, key) => ActivityStatusNotifier(
    config: ref.watch(activityStatusConfigProvider),
    serverId: key.serverId,
    roomId: key.roomId,
  ),
);

/// Active activity status state for current room.
///
/// Convenience provider that derives from [roomActivityStatusProvider] using
/// [activeServerRoomKeyProvider]. Returns empty state if no room selected.
final activeActivityStatusProvider = Provider<ActivityStatusState>((ref) {
  final key = ref.watch(activeServerRoomKeyProvider);
  if (key == null) return const ActivityStatusState();
  return ref.watch(roomActivityStatusProvider(key));
});

/// Active activity status notifier for current room.
///
/// Returns the notifier for the current room, or null if no room selected.
/// Use this to modify activity status state.
final activeActivityStatusNotifierProvider =
    Provider<ActivityStatusNotifier?>((ref) {
  final key = ref.watch(activeServerRoomKeyProvider);
  if (key == null) return null;
  return ref.read(roomActivityStatusProvider(key).notifier);
});

/// Legacy provider for activity status state (server-scoped only).
///
/// DEPRECATED: Prefer [roomActivityStatusProvider] for per-room state.
/// Kept for backward compatibility during migration.
final activityStatusProvider =
    StateNotifierProvider<ActivityStatusNotifier, ActivityStatusState>((ref) {
  final config = ref.watch(activityStatusConfigProvider);
  final server = ref.watch(currentServerFromAppStateProvider);
  final roomId = ref.watch(selectedRoomProvider);
  return ActivityStatusNotifier(config: config, serverId: server?.id, roomId: roomId);
});
