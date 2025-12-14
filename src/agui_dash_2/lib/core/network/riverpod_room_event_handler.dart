import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/panel_providers.dart';
import 'room_event_handler.dart';
import 'server_room_key.dart';

/// Room event handler that updates Riverpod state.
///
/// Decouples session logic from UI widgets by directly updating the
/// corresponding providers for the given [ServerRoomKey].
class RiverpodRoomEventHandler implements RoomEventHandler {
  final Ref ref;
  final ServerRoomKey key;

  RiverpodRoomEventHandler(this.ref, this.key);

  @override
  void onCanvasUpdate(
    String operation,
    String widgetName,
    Map<String, dynamic> data,
  ) {
    // Update Canvas
    final canvasNotifier = ref.read(roomCanvasProvider(key).notifier);
    switch (operation) {
      case 'clear':
        canvasNotifier.clear();
      case 'replace':
        canvasNotifier.replaceAll(widgetName, data);
      default:
        canvasNotifier.addItem(widgetName, data);
    }

    // Log to Context Pane
    final contextNotifier = ref.read(roomContextPaneProvider(key).notifier);
    contextNotifier.addCanvasRender(widgetName, operation);
  }

  @override
  void onContextUpdate(
    String eventType, {
    String? summary,
    Map<String, dynamic>? data,
  }) {
    final notifier = ref.read(roomContextPaneProvider(key).notifier);

    switch (eventType) {
      case 'userMessage':
        notifier.addTextMessage(summary ?? '', isUser: true);
      case 'textMessage':
        notifier.addTextMessage(summary ?? '', isUser: false);
      case 'runStarted':
        notifier.addAgUiEvent('Run Started', summary: summary);
      case 'runFinished':
        notifier.addAgUiEvent('Run Finished');
      case 'toolCall':
        notifier.addToolCall(summary ?? 'tool', summary: 'started');
      case 'toolResult':
        notifier.addAgUiEvent('Tool Result');
      case 'genUiRender':
        notifier.addGenUiRender(summary ?? 'Widget');
      case 'stateSnapshot':
        if (data != null) notifier.updateState(data);
      case 'stateDelta':
        if (data != null) notifier.applyDelta(data);
      case 'thinking':
        notifier.addAgUiEvent('Thinking');
      case 'error':
        notifier.addAgUiEvent('Error', summary: summary);
      case 'localToolExecution':
        final parts = summary?.split(': ') ?? [];
        if (parts.length >= 2) {
          notifier.addLocalToolExecution(parts[0], status: parts[1]);
        }
    }
  }

  @override
  void onActivityUpdate(bool isActive, {String? eventType, String? toolName}) {
    final notifier = ref.read(roomActivityStatusProvider(key).notifier);

    if (isActive) {
      if (eventType != null) {
        notifier.handleEvent(eventType, toolName: toolName);
      } else {
        notifier.startActivity();
      }
    } else {
      notifier.stopActivity();
    }
  }

  @override
  void onToolExecution(
    String toolCallId,
    String toolName,
    String status, {
    String? errorMessage,
  }) {
    final notifier = ref.read(roomToolExecutionProvider(key).notifier);

    switch (status) {
      case 'executing':
        notifier.startExecution(toolCallId, toolName);
      case 'completed':
        notifier.endExecution(toolCallId);
      default:
        // Handle 'error' or any error status
        if (status.startsWith('error')) {
          notifier.endExecution(toolCallId);
        }
    }
  }
}
