/// Centralized provider declarations for server-scoped panel state.
///
/// All panel providers are declared here and MUST watch [currentServerFromAppStateProvider].
/// This ensures automatic state reset when switching servers.
///
/// When adding a new panel:
/// 1. Create a notifier that extends [ServerScopedNotifier]
/// 2. Add the provider declaration here
/// 3. Make sure it watches [currentServerFromAppStateProvider]
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/activity_status_service.dart';
import '../services/canvas_service.dart';
import '../services/chat_service.dart';
import '../services/context_pane_service.dart';
import 'app_providers.dart';

// =============================================================================
// CHAT PANEL
// =============================================================================

/// Provider for chat state.
///
/// Watches [currentServerFromAppStateProvider] - chat clears when server changes.
final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  final server = ref.watch(currentServerFromAppStateProvider);
  return ChatNotifier(serverId: server?.id);
});

// =============================================================================
// CANVAS PANEL
// =============================================================================

/// Provider for canvas state.
///
/// Watches [currentServerFromAppStateProvider] - canvas clears when server changes.
final canvasProvider = StateNotifierProvider<CanvasNotifier, CanvasState>((ref) {
  final server = ref.watch(currentServerFromAppStateProvider);
  return CanvasNotifier(serverId: server?.id);
});

// =============================================================================
// CONTEXT PANE
// =============================================================================

/// Provider for context pane state.
///
/// Watches [currentServerFromAppStateProvider] - context pane clears when server changes.
final contextPaneProvider =
    StateNotifierProvider<ContextPaneNotifier, ContextPaneState>((ref) {
  final server = ref.watch(currentServerFromAppStateProvider);
  return ContextPaneNotifier(serverId: server?.id);
});

// =============================================================================
// ACTIVITY STATUS
// =============================================================================

/// Provider for activity status state.
///
/// Watches [currentServerFromAppStateProvider] - activity stops when server changes.
final activityStatusProvider =
    StateNotifierProvider<ActivityStatusNotifier, ActivityStatusState>((ref) {
  final config = ref.watch(activityStatusConfigProvider);
  final server = ref.watch(currentServerFromAppStateProvider);
  return ActivityStatusNotifier(config: config, serverId: server?.id);
});
