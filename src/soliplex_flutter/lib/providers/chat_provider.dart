import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../client/client.dart';
import 'canvas_provider.dart';
import 'client_provider.dart';
import 'room_provider.dart';
import 'thread_provider.dart';

/// Provider for sending chat messages.
///
/// Returns a function that sends a message and handles the full conversation flow.
final sendMessageProvider = Provider<Future<void> Function(String)>((ref) {
  final client = ref.watch(soliplexClientProvider);
  final roomId = ref.watch(currentRoomProvider);
  final canvasNotifier = ref.watch(canvasStateProvider.notifier);
  final activityNotifier = ref.watch(isAgentActiveProvider.notifier);

  return (String message) async {
    if (roomId == null) {
      throw StateError('No room selected');
    }

    await client.chat(
      roomId: roomId,
      userMessage: message,
      onCanvasUpdate: (data) {
        canvasNotifier.updateState(data);
      },
      onActivityUpdate: (isActive) {
        activityNotifier.state = isActive;
      },
    );

    // Refresh threads list after chat (may have created new thread)
    ref.invalidate(threadsProvider);
  };
});

/// Provider for sending chat messages with tools.
final sendMessageWithToolsProvider = Provider<
  Future<void> Function(
    String message, {
    Map<String, ag_ui.Tool>? tools,
    Map<String, ToolExecutor>? toolExecutors,
    UiToolHandler? uiToolHandler,
    Map<String, dynamic>? state,
  })
>((ref) {
  final client = ref.watch(soliplexClientProvider);
  final roomId = ref.watch(currentRoomProvider);
  final canvasNotifier = ref.watch(canvasStateProvider.notifier);
  final activityNotifier = ref.watch(isAgentActiveProvider.notifier);

  return (
    String message, {
    Map<String, ag_ui.Tool>? tools,
    Map<String, ToolExecutor>? toolExecutors,
    UiToolHandler? uiToolHandler,
    Map<String, dynamic>? state,
  }) async {
    if (roomId == null) {
      throw StateError('No room selected');
    }

    await client.chat(
      roomId: roomId,
      userMessage: message,
      tools: tools,
      toolExecutors: toolExecutors,
      uiToolHandler: uiToolHandler,
      state: state,
      onCanvasUpdate: (data) {
        canvasNotifier.updateState(data);
      },
      onActivityUpdate: (isActive) {
        activityNotifier.state = isActive;
      },
    );

    // Refresh threads list after chat
    ref.invalidate(threadsProvider);
  };
});

/// Provider for cancelling the current run.
final cancelRunProvider = Provider<void Function()>((ref) {
  final client = ref.watch(soliplexClientProvider);
  final roomId = ref.watch(currentRoomProvider);

  return () {
    if (roomId != null) {
      client.cancelRun(roomId);
    }
  };
});
