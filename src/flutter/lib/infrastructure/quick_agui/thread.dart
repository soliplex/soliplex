import 'package:ag_ui/ag_ui.dart' as ag_ui;

class Thread {
  final String id;
  final List<ag_ui.Run> _runs = [];

  Thread({required this.id});

  Iterable<ag_ui.Run> get runs => _runs;

  void startRun({required String runId, required ag_ui.UserMessage message}) {
    final run = ag_ui.Run(threadId: id, runId: runId);
    _runs.add(run);
  }
}
