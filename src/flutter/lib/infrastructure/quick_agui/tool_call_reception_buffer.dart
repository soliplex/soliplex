class ToolCallReceptionBuffer {
  final String name;
  final StringBuffer _argsBuffer;

  ToolCallReceptionBuffer(this.name) : _argsBuffer = StringBuffer();

  void appendArgs(String delta) {
    _argsBuffer.write(delta);
  }

  String get args => _argsBuffer.toString();
}