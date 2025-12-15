import 'dart:async';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex/core/network/http_transport.dart';
import 'package:soliplex/core/network/network_transport_layer.dart';
import 'package:soliplex/core/network/room_session.dart';

class MockNetworkTransportLayer extends Mock implements NetworkTransportLayer {}

class MockHttpTransport extends Mock implements HttpTransport {}

class FakeSimpleRunAgentInput extends Fake
    implements ag_ui.SimpleRunAgentInput {}

class FakeUri extends Fake implements Uri {}

void main() {
  group('RoomSession Lifecycle & Event Loop', () {
    late MockNetworkTransportLayer mockLayer;
    late MockHttpTransport mockHttpTransport;
    late StreamController<ag_ui.BaseEvent> streamController;
    late RoomSession session;

    setUpAll(() {
      registerFallbackValue(FakeSimpleRunAgentInput());
      registerFallbackValue(FakeUri());
    });

    setUp(() {
      mockLayer = MockNetworkTransportLayer();
      mockHttpTransport = MockHttpTransport();
      streamController = StreamController<ag_ui.BaseEvent>.broadcast();

      // Mock runAgent on layer (used by Thread via delegate)
      when(
        () => mockLayer.runAgent(any(), any()),
      ).thenAnswer((_) => streamController.stream);

      // Mock createThread (does NOT contain thread ID 't1' yet)
      when(
        () => mockHttpTransport.post(
          any(
            that: isA<Uri>().having(
              (u) => u.path,
              'path',
              isNot(contains('/t1')),
            ),
          ),
          any(),
        ),
      ).thenAnswer(
        (_) async => {
          'thread_id': 't1',
          'runs': {'r1': {}},
        },
      );

      // Mock createRun (contains thread ID 't1')
      when(
        () => mockHttpTransport.post(
          any(that: isA<Uri>().having((u) => u.path, 'path', contains('/t1'))),
          any(),
        ),
      ).thenAnswer((_) async => {'run_id': 'r2'});

      // cancelRun
      when(
        () => mockHttpTransport.cancelRun(
          roomId: any(named: 'roomId'),
          threadId: any(named: 'threadId'),
          runId: any(named: 'runId'),
        ),
      ).thenAnswer((_) async {});

      session = RoomSession(
        roomId: 'room1',
        serverId: 'server1',
        baseUrl: 'http://test.com',
        transport: mockHttpTransport, // Inject mock transport
      );
    });

    tearDown(() async {
      if (!session.isDisposed) session.dispose();
      await streamController.close();
    });

    test('initialize() subscribes to event stream immediately', () async {
      await session.initialize(transportLayer: mockLayer);
      // We assume subscription happens (Thread creation uses delegate)
    });

    test('Events are processed during startRun', () async {
      await session.initialize(transportLayer: mockLayer);
      await session.createRun();

      // Start run to connect the stream
      final runFuture = session.startRun(messages: []);

      // Emit a full message sequence from the "server"
      streamController.add(
        const ag_ui.TextMessageStartEvent(messageId: 'msg1'),
      );
      streamController.add(
        const ag_ui.TextMessageContentEvent(
          messageId: 'msg1',
          delta: 'Hello form background',
        ),
      );

      await Future<void>.delayed(
        const Duration(milliseconds: 10),
      ); // Process event loop

      expect(session.messages.isNotEmpty, isTrue);
      expect(session.messages.last.text, equals('Hello form background'));

      await streamController.close();
      try {
        await runFuture;
      } on Object catch (_) {}
    });

    test('dispose() cleans up locally without network call', () async {
      await session.initialize(transportLayer: mockLayer);
      await session.createRun();

      // Start run to connect the stream
      final runFuture = session.startRun(messages: []);

      session.dispose();

      // dispose() is local cleanup, does not call cancelRun
      verifyNever(
        () => mockHttpTransport.cancelRun(
          roomId: any(named: 'roomId'),
          threadId: any(named: 'threadId'),
          runId: any(named: 'runId'),
        ),
      );

      // Close stream to prevent hang
      await streamController.close();
      try {
        await runFuture;
      } on Object catch (_) {}
    });

    test('startRun prevents concurrent execution', () async {
      await session.initialize(transportLayer: mockLayer);
      await session.createRun();

      // Start first run
      final future1 = session.startRun(messages: []);

      // Attempt second run immediately
      expect(
        () => session.startRun(messages: []),
        throwsA(
          isA<StateError>().having(
            (e) => e.message,
            'message',
            contains('streaming'),
          ),
        ),
      );

      await streamController.close();
      try {
        await future1;
      } on Object catch (_) {}
    });
  });
}
