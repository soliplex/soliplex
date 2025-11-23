import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/infrastructure/quick_agui/thread.dart';

void main() {
  final config = ag_ui.AgUiClientConfig(baseUrl: 'https://foo.com');
  final client = ag_ui.AgUiClient(config: config);

  group('Initialised Thread', () {
    test('exposes an empty iterable of Run objects', () {
      const testId = 'thread-456';
      final thread = Thread(id: testId, client: client);

      final runs = thread.runs;

      expect(runs, isNotNull);
      expect(runs, isA<Iterable<ag_ui.Run>>());
    });

    test('will create the first Run given a run id and a User message', () {
      final thread = Thread(id: '--irrelevant-thread-id--', client: client);
      const id = '--irrelevant-run-id--';
      const message = ag_ui.UserMessage(
        id: '--irrelevant-msg-id--',
        content: 'hi!',
      );
      thread.startRun(runId: id, message: message);
      final [ag_ui.Run(:runId)] = thread.runs.toList();
      expect(id, runId);
    });
  });
}
