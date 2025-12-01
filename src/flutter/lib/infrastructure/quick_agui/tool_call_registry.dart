import 'package:ag_ui/ag_ui.dart';

class ToolCallRegistry {
  final Map<String, ToolCall> _calls = {};
  final Map<String, ToolMessage> _results = {};

  void register(ToolCall call) {
    _calls[call.id] = call;
  }

  void markCompleted(String toolCallId, ToolMessage message) {
    _results[toolCallId] = message;
    _calls.remove(toolCallId);
  }

  Iterable<ToolMessage> get results => _results.values;

  Iterable<ToolCall> get pendingCalls => _calls.values;
}
