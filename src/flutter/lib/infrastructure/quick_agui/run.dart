import 'package:ag_ui/ag_ui.dart' hide Run;

typedef Messages = List<Message>;

class Run {
  final String id;
  final Messages messages = [];

  Run({required this.id});
}
