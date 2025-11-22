import 'package:ag_ui/ag_ui.dart';
import 'package:json_patch/json_patch.dart';
import 'parse_result.dart';

/// Accumulates a tool call as events stream in
class _PendingToolCall {
  final String name;
  final StringBuffer argsBuffer;

  _PendingToolCall(this.name) : argsBuffer = StringBuffer();

  void appendArgs(String delta) {
    argsBuffer.write(delta);
  }

  String get args => argsBuffer.toString();
}

/// Stateless parser that transforms AG-UI events into ParseResults.
///
/// The parser maintains accumulation buffers for chunked events (text, tool args)
/// but does NOT maintain domain state. State management is the caller's responsibility.
class EventParser {
  // Parsing state (accumulation buffers for chunked events)
  final StringBuffer _textBuffer = StringBuffer();
  final Map<String, _PendingToolCall> _pendingToolCalls = {};

  /// Process an AG-UI event and return a ParseResult.
  ///
  /// For state delta events, the current state must be provided to apply the patch.
  ParseResult processEvent(BaseEvent event, {Map<String, dynamic>? currentState}) {
    switch (event) {
      // === MESSAGE EVENTS ===
      case TextMessageStartEvent():
        _textBuffer.clear();
        return NoResult();

      case TextMessageContentEvent(delta: final delta):
        _textBuffer.write(delta);
        return NoResult();

      case TextMessageEndEvent():
        final msg = AssistantMessage(
          id: _generateId(),
          content: _textBuffer.toString(),
        );
        _textBuffer.clear();
        return MessageResult(msg);

      case TextMessageChunkEvent(delta: final delta?):
        return MessageResult(AssistantMessage(id: _generateId(), content: delta));

      case TextMessageChunkEvent():
        return NoResult();

      // === TOOL CALL EVENTS ===
      case ToolCallStartEvent(toolCallId: final id, toolCallName: final name):
        _pendingToolCalls[id] = _PendingToolCall(name);
        return NoResult();

      case ToolCallArgsEvent(toolCallId: final id, delta: final delta):
        _pendingToolCalls[id]?.appendArgs(delta);
        return NoResult();

      case ToolCallEndEvent(toolCallId: final id):
        final pending = _pendingToolCalls.remove(id);

        if (pending == null) return NoResult();

        return MessageResult(
          AssistantMessage(
            id: _generateId(),
            toolCalls: [
              ToolCall(
                id: id,
                function: FunctionCall(
                  name: pending.name,
                  arguments: pending.args.isEmpty ? '{}' : pending.args,
                ),
              ),
            ],
          ),
        );

      case ToolCallResultEvent(toolCallId: final id, content: final content):
        return MessageResult(
          ToolMessage(id: _generateId(), toolCallId: id, content: content),
        );

      // === STATE EVENTS ===
      case StateSnapshotEvent(snapshot: final snapshot):
        return StateUpdateResult(snapshot as Map<String, dynamic>);

      case StateDeltaEvent(delta: final delta):
        if (currentState == null) {
          throw StateError(
            'Received StateDelta event but no currentState provided to parser',
          );
        }

        final operations = delta.cast<Map<String, dynamic>>();
        final patched = JsonPatch.apply(currentState, operations) as Map<String, dynamic>;
        return StateUpdateResult(patched);

      // === THINKING EVENTS ===
      case ThinkingContentEvent(delta: final delta):
        return ThinkingResult(delta, DateTime.now());

      case ThinkingStartEvent():
        return NoResult();

      case ThinkingEndEvent():
        return NoResult();

      // === LIFECYCLE EVENTS ===
      case RunStartedEvent():
        return LifecycleResult(RunLifecycle.started);

      case RunFinishedEvent():
        return LifecycleResult(RunLifecycle.finished);

      case RunErrorEvent():
        return LifecycleResult(RunLifecycle.error);

      // === UNHANDLED ===
      default:
        return NoResult();
    }
  }

  String _generateId() => 'msg_${DateTime.now().millisecondsSinceEpoch}';
}
