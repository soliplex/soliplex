import 'run.dart';

class Thread {
  final String id;
  final List<Run> _runs = [];

  Thread({required this.id});

  Iterable<Run> get runs => _runs;
}
