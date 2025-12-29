import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex/core/network/room_event_handler.dart';
import 'package:soliplex/core/network/server_room_key.dart';
import 'package:soliplex/core/protocol/agui_event_types.dart'; // Import AgUiEventTypes
import 'package:soliplex/core/providers/panel_providers.dart';

/// Room event handler that updates Riverpod state.
///
/// Decouples session logic from UI widgets by directly updating the
/// corresponding providers for the given ServerRoomKey.
class RiverpodRoomEventHandler implements RoomEventHandler {
  RiverpodRoomEventHandler(this.ref, this.key);
  final Ref ref;
  final ServerRoomKey key;

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
      case AgUiEventTypes.userMessage:
        notifier.addTextMessage(summary ?? '', isUser: true);
      case AgUiEventTypes.textMessage:
        notifier.addTextMessage(summary ?? '');
      case AgUiEventTypes.runStarted:
        notifier.addAgUiEvent('Run Started', summary: summary);
      case AgUiEventTypes.runFinished:
        notifier.addAgUiEvent('Run Finished');
      case AgUiEventTypes.toolCallStart:
        notifier.addToolCall(summary ?? 'tool', summary: 'started');
      case AgUiEventTypes.toolResult:
        notifier.addAgUiEvent('Tool Result');
      case AgUiEventTypes.genUiRender:
        notifier.addGenUiRender(summary ?? 'Widget');
      case AgUiEventTypes.stateSnapshot:
        if (data != null) notifier.updateState(data);
      case AgUiEventTypes.stateDelta:
        if (data != null) notifier.applyDelta(data);
      case AgUiEventTypes.thinking:
        notifier.addAgUiEvent('Thinking');
      case AgUiEventTypes.runError:
        notifier.addAgUiEvent('Error', summary: summary);
      case AgUiEventTypes.localToolExecution:
        final parts = summary?.split(': ') ?? [];
        if (parts.length >= 2) {
          notifier.addLocalToolExecution(parts[0], status: parts[1]);
        }
    }
  }

  @override
  void onActivityUpdate({
    bool isActive = false,
    String? eventType,
    String? toolName,
  }) {
    final notifier = ref.read(roomActivityStatusProvider(key).notifier);

    if (isActive) {
      if (eventType != null) {
        notifier.handleEvent(eventType: eventType, toolName: toolName);
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
