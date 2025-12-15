import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/core/network/room_event_handler.dart';

void main() {
  group('RoomEventHandler', () {
    group('NoOpRoomEventHandler', () {
      test('can be instantiated as const', () {
        const handler = NoOpRoomEventHandler();
        expect(handler, isNotNull);
      });

      test('onCanvasUpdate does nothing', () {
        const handler = NoOpRoomEventHandler();
        // Should not throw
        handler.onCanvasUpdate('add', 'widget', {'key': 'value'});
      });

      test('onContextUpdate does nothing', () {
        const handler = NoOpRoomEventHandler();
        // Should not throw
        handler.onContextUpdate('runStarted', summary: 'test');
        handler.onContextUpdate('stateSnapshot', data: {'key': 'value'});
      });

      test('onActivityUpdate does nothing', () {
        const handler = NoOpRoomEventHandler();
        // Should not throw
        handler.onActivityUpdate(isActive: true, eventType: 'TextMessageStart');
        handler.onActivityUpdate(isActive: false, eventType: 'stop');
      });
    });

    group('RecordingRoomEventHandler', () {
      late RecordingRoomEventHandler handler;

      setUp(() {
        handler = RecordingRoomEventHandler();
      });

      test('records canvas updates', () {
        handler.onCanvasUpdate('add', 'widget1', {'id': '1'});
        handler.onCanvasUpdate('clear', 'widget2', {});

        expect(handler.canvasUpdates, hasLength(2));
        expect(handler.canvasUpdates[0].operation, equals('add'));
        expect(handler.canvasUpdates[0].widgetName, equals('widget1'));
        expect(handler.canvasUpdates[0].data, equals({'id': '1'}));
        expect(handler.canvasUpdates[1].operation, equals('clear'));
      });

      test('records context updates', () {
        handler.onContextUpdate('runStarted', summary: 'run-1');
        handler.onContextUpdate('stateSnapshot', data: {'count': 5});
        handler.onContextUpdate('error');

        expect(handler.contextUpdates, hasLength(3));
        expect(handler.contextUpdates[0].eventType, equals('runStarted'));
        expect(handler.contextUpdates[0].summary, equals('run-1'));
        expect(handler.contextUpdates[0].data, isNull);
        expect(handler.contextUpdates[1].eventType, equals('stateSnapshot'));
        expect(handler.contextUpdates[1].data, equals({'count': 5}));
        expect(handler.contextUpdates[2].eventType, equals('error'));
      });

      test('records activity updates', () {
        handler.onActivityUpdate(
          isActive: true,
          eventType: 'ToolCallStart',
          toolName: 'get_location',
        );
        handler.onActivityUpdate(isActive: false, eventType: 'stop');

        expect(handler.activityUpdates, hasLength(2));
        expect(handler.activityUpdates[0].isActive, isTrue);
        expect(handler.activityUpdates[0].eventType, equals('ToolCallStart'));
        expect(handler.activityUpdates[0].toolName, equals('get_location'));
        expect(handler.activityUpdates[1].isActive, isFalse);
        expect(handler.activityUpdates[1].eventType, equals('stop'));
      });

      test('clear removes all recorded events', () {
        handler.onCanvasUpdate('add', 'w', {});
        handler.onContextUpdate('test');
        handler.onActivityUpdate(isActive: true, eventType: 'start');

        expect(handler.canvasUpdates, isNotEmpty);
        expect(handler.contextUpdates, isNotEmpty);
        expect(handler.activityUpdates, isNotEmpty);

        handler.clear();

        expect(handler.canvasUpdates, isEmpty);
        expect(handler.contextUpdates, isEmpty);
        expect(handler.activityUpdates, isEmpty);
      });
    });

    group('Record classes', () {
      test('CanvasUpdateRecord stores all fields', () {
        final record = CanvasUpdateRecord('replace', 'myWidget', {
          'foo': 'bar',
        });
        expect(record.operation, equals('replace'));
        expect(record.widgetName, equals('myWidget'));
        expect(record.data, equals({'foo': 'bar'}));
      });

      test('ContextUpdateRecord stores all fields', () {
        final record = ContextUpdateRecord('toolCall', 'summary text', {
          'detail': 123,
        });
        expect(record.eventType, equals('toolCall'));
        expect(record.summary, equals('summary text'));
        expect(record.data, equals({'detail': 123}));
      });

      test('ContextUpdateRecord handles null optional fields', () {
        final record = ContextUpdateRecord('runFinished', null, null);
        expect(record.eventType, equals('runFinished'));
        expect(record.summary, isNull);
        expect(record.data, isNull);
      });

      test('ActivityUpdateRecord stores all fields', () {
        final record = ActivityUpdateRecord(
          isActive: true,
          eventType: 'ThinkingStart',
          toolName: 'think_tool',
        );
        expect(record.isActive, isTrue);
        expect(record.eventType, equals('ThinkingStart'));
        expect(record.toolName, equals('think_tool'));
      });

      test('ActivityUpdateRecord handles null optional fields', () {
        final record = ActivityUpdateRecord(isActive: false, eventType: 'stop', toolName: null); // ignore: lines_longer_than_80_chars
        expect(record.isActive, isFalse);
        expect(record.eventType, equals('stop'));
        expect(record.toolName, isNull);
      });
    });
  });
}
