import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/infrastructure/quick_agui/thread.dart';

class AgUiClientMock extends Mock implements ag_ui.AgUiClient {}

void main() {
  setUpAll(() {
    registerFallbackValue(
      ag_ui.SimpleRunAgentInput(
        threadId: '--irrelevant-thread-id--',
        runId: '--irrelevant-run-id--',
        messages: [],
      ),
    );
  });

  late ag_ui.AgUiClient client;

  setUp(() {
    client = AgUiClientMock();
  });

  group('Initialised Thread', () {
    test('exposes an empty iterable of Run objects', () {
      const testId = 'thread-456';
      final thread = Thread(id: testId, client: client);

      final runs = thread.runs;

      expect(runs, isNotNull);
      expect(runs, isA<Iterable<ag_ui.Run>>());
    });

    test('startRun tracks the first run', () {
      final thread = Thread(id: '--irrelevant-thread-id--', client: client);

      when(
        () => client.runAgent(any(), any()),
      ).thenAnswer((_) => Stream.empty());

      thread.startRun(
        runId: '--irrelevant-run-id--',
        message: ag_ui.UserMessage(id: 'msg-id-1', content: 'hi!'),
      );

      final [ag_ui.Run(runId: capturedRunId)] = thread.runs.toList();
      expect(capturedRunId, '--irrelevant-run-id--');
    });

    test('one text message chunk', () async {
      const threadId = '--irrelevant-thread-id--';
      const runId = '--irrelevant-run-id--';
      when(() => client.runAgent(any(), any())).thenAnswer(
        (_) => Stream.fromIterable([
          ag_ui.RunStartedEvent(threadId: threadId, runId: runId),
          ag_ui.TextMessageChunkEvent(
            messageId: 'msg-id-2',
            delta: "hi! What can I do?",
          ),
          ag_ui.RunFinishedEvent(threadId: threadId, runId: runId),
        ]),
      );

      final thread = Thread(id: threadId, client: client);
      final publishedMessages = thread.messageStream.take(2).toList();
      thread.startRun(
        runId: runId,
        message: ag_ui.UserMessage(id: 'msg-id-1', content: 'hi!'),
      );

      final [msg1, msg2] = await publishedMessages;
      expect(
        msg1,
        isA<ag_ui.UserMessage>()
            .having((m) => m.content, "content", equals('hi!'))
            .having((m) => m.id, "message id", equals("msg-id-1")),
      );
      expect(
        msg2,
        isA<ag_ui.AssistantMessage>()
            .having((m) => m.content, "content", equals("hi! What can I do?"))
            .having((m) => m.id, "message id", equals("msg-id-2")),
      );
    }, timeout: Timeout(Duration(seconds: 2)));
  });
}
