import 'package:ag_ui/ag_ui.dart' as ag_ui;

/// Buffer for accumulating streaming tool call arguments.
class ToolCallReceptionBuffer {
  ToolCallReceptionBuffer(this.id, this.name);

  final String id;
  final String name;
  final StringBuffer _argsBuffer = StringBuffer();

  /// Append arguments to the buffer.
  void appendArgs(String delta) {
    _argsBuffer.write(delta);
  }

  /// Get the accumulated arguments.
  String get args => _argsBuffer.toString();

  /// Get the tool call.
  ag_ui.ToolCall get toolCall => ag_ui.ToolCall(
    id: id,
    function: ag_ui.FunctionCall(
      name: name,
      arguments: args.isEmpty ? '{}' : args,
    ),
  );

  /// Get the assistant message containing this tool call.
  ag_ui.AssistantMessage get message =>
      ag_ui.AssistantMessage(id: 'msg_$id', toolCalls: [toolCall]);

  @override
  String toString() => 'ToolCallReceptionBuffer(id: $id, name: $name)';
}
