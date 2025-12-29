import 'package:ag_ui/ag_ui.dart' as ag_ui;

/// Buffer for accumulating streamed tool call arguments.
class ToolCallReceptionBuffer {
  ToolCallReceptionBuffer(this.id, this.name) : _argsBuffer = StringBuffer();
  final String id;
  final String name;
  final StringBuffer _argsBuffer;

  void appendArgs(String delta) {
    _argsBuffer.write(delta);
  }

  String get args => _argsBuffer.toString();

  ag_ui.ToolCall get toolCall => ag_ui.ToolCall(
    id: id,
    function: ag_ui.FunctionCall(
      name: name,
      arguments: args.isEmpty ? '{}' : args,
    ),
  );

  ag_ui.AssistantMessage get message =>
      ag_ui.AssistantMessage(id: 'msg_$id', toolCalls: [toolCall]);
}
