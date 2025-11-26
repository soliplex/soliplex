import 'package:ag_ui/ag_ui.dart' as ag_ui;

class ToolCallReceptionBuffer {
  final String id;
  final String name;
  final StringBuffer _argsBuffer;

  ToolCallReceptionBuffer(this.id, this.name) : _argsBuffer = StringBuffer();

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

  ag_ui.AssistantMessage get message => ag_ui.AssistantMessage(
    // TODO: may need to get msg some other way (generate it or retrieve it from server).
    id: 'msg_$id',
    toolCalls:
        // TODO: handle cases when there are multiple tool calls in one message.
        [toolCall],
  );
}
