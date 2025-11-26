import 'package:ag_ui/ag_ui.dart';

class ToolCallRegistry {
  final Map<String, ToolCall> _calls = {};

  void register(ToolCall call) {
    _calls[call.id] = call;
  }

  void markCompleted(String toolCallId) {
    _calls.remove(toolCallId);
  }

  Iterable<ToolCall> get pendingCalls => _calls.values;
}
