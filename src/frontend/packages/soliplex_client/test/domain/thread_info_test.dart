import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('ThreadInfo', () {
    test('creates with required fields', () {
      final createdAt = DateTime(2025);
      final updatedAt = DateTime(2025, 1, 2);
      final thread = ThreadInfo(
        id: 'thread-1',
        roomId: 'room-1',
        createdAt: createdAt,
        updatedAt: updatedAt,
      );

      expect(thread.id, equals('thread-1'));
      expect(thread.roomId, equals('room-1'));
      expect(thread.initialRunId, equals(''));
      expect(thread.name, equals(''));
      expect(thread.description, equals(''));
      expect(thread.createdAt, equals(createdAt));
      expect(thread.updatedAt, equals(updatedAt));
      expect(thread.metadata, equals(const <String, dynamic>{}));
      expect(thread.hasInitialRun, isFalse);
      expect(thread.hasName, isFalse);
      expect(thread.hasDescription, isFalse);
    });

    test('creates with all fields', () {
      final createdAt = DateTime(2025);
      final updatedAt = DateTime(2025, 1, 2);
      final thread = ThreadInfo(
        id: 'thread-1',
        roomId: 'room-1',
        initialRunId: 'run-1',
        name: 'Test Thread',
        description: 'A test thread',
        createdAt: createdAt,
        updatedAt: updatedAt,
        metadata: const {'key': 'value'},
      );

      expect(thread.id, equals('thread-1'));
      expect(thread.roomId, equals('room-1'));
      expect(thread.initialRunId, equals('run-1'));
      expect(thread.name, equals('Test Thread'));
      expect(thread.description, equals('A test thread'));
      expect(thread.createdAt, equals(createdAt));
      expect(thread.updatedAt, equals(updatedAt));
      expect(thread.metadata, equals({'key': 'value'}));
      expect(thread.hasInitialRun, isTrue);
      expect(thread.hasName, isTrue);
      expect(thread.hasDescription, isTrue);
    });

    group('fromJson', () {
      test('parses correctly with all fields', () {
        final json = <String, dynamic>{
          'id': 'thread-1',
          'room_id': 'room-1',
          'initial_run_id': 'run-1',
          'name': 'Test Thread',
          'description': 'A test thread',
          'created_at': '2025-01-01T00:00:00.000Z',
          'updated_at': '2025-01-02T00:00:00.000Z',
          'metadata': {'key': 'value'},
        };

        final thread = ThreadInfo.fromJson(json);

        expect(thread.id, equals('thread-1'));
        expect(thread.roomId, equals('room-1'));
        expect(thread.initialRunId, equals('run-1'));
        expect(thread.name, equals('Test Thread'));
        expect(thread.description, equals('A test thread'));
        expect(thread.createdAt, isNotNull);
        expect(thread.updatedAt, isNotNull);
        expect(thread.metadata, equals({'key': 'value'}));
      });

      test('parses correctly with only required fields', () {
        final json = <String, dynamic>{
          'id': 'thread-1',
          'room_id': 'room-1',
        };

        final thread = ThreadInfo.fromJson(json);

        expect(thread.id, equals('thread-1'));
        expect(thread.roomId, equals('room-1'));
        expect(thread.initialRunId, equals(''));
        expect(thread.name, equals(''));
        expect(thread.description, equals(''));
        expect(thread.createdAt, isNotNull);
        expect(thread.updatedAt, isNotNull);
        expect(thread.metadata, equals(const <String, dynamic>{}));
      });

      test('handles thread_id field', () {
        final json = <String, dynamic>{
          'thread_id': 'thread-1',
          'room_id': 'room-1',
        };

        final thread = ThreadInfo.fromJson(json);

        expect(thread.id, equals('thread-1'));
      });

      test('handles missing room_id', () {
        final json = <String, dynamic>{
          'id': 'thread-1',
        };

        final thread = ThreadInfo.fromJson(json);

        expect(thread.roomId, equals(''));
      });

      test('handles invalid created_at DateTime', () {
        final json = <String, dynamic>{
          'id': 'thread-1',
          'room_id': 'room-1',
          'created_at': 'invalid-date',
        };

        final thread = ThreadInfo.fromJson(json);

        expect(thread.createdAt, isNotNull);
      });

      test('handles invalid updated_at DateTime', () {
        final json = <String, dynamic>{
          'id': 'thread-1',
          'room_id': 'room-1',
          'created_at': '2025-01-01T00:00:00.000Z',
          'updated_at': 'invalid-date',
        };

        final thread = ThreadInfo.fromJson(json);

        expect(thread.updatedAt, isNotNull);
        expect(thread.updatedAt, equals(thread.createdAt));
      });

      test('handles null optional fields', () {
        final json = <String, dynamic>{
          'id': 'thread-1',
          'room_id': 'room-1',
          'initial_run_id': null,
          'name': null,
          'description': null,
          'metadata': null,
        };

        final thread = ThreadInfo.fromJson(json);

        expect(thread.initialRunId, equals(''));
        expect(thread.name, equals(''));
        expect(thread.description, equals(''));
        expect(thread.metadata, equals(const <String, dynamic>{}));
      });
    });

    group('toJson', () {
      test('serializes correctly with all fields', () {
        final createdAt = DateTime.utc(2025);
        final updatedAt = DateTime.utc(2025, 1, 2);
        final thread = ThreadInfo(
          id: 'thread-1',
          roomId: 'room-1',
          initialRunId: 'run-1',
          name: 'Test Thread',
          description: 'A test thread',
          createdAt: createdAt,
          updatedAt: updatedAt,
          metadata: const {'key': 'value'},
        );

        final json = thread.toJson();

        expect(json['id'], equals('thread-1'));
        expect(json['room_id'], equals('room-1'));
        expect(json['initial_run_id'], equals('run-1'));
        expect(json['name'], equals('Test Thread'));
        expect(json['description'], equals('A test thread'));
        expect(json['created_at'], equals('2025-01-01T00:00:00.000Z'));
        expect(json['updated_at'], equals('2025-01-02T00:00:00.000Z'));
        expect(json['metadata'], equals({'key': 'value'}));
      });

      test('excludes empty fields', () {
        final thread = ThreadInfo(
          id: 'thread-1',
          roomId: 'room-1',
          createdAt: DateTime.utc(2025),
          updatedAt: DateTime.utc(2025),
        );

        final json = thread.toJson();

        expect(json.containsKey('id'), isTrue);
        expect(json.containsKey('room_id'), isTrue);
        expect(json.containsKey('created_at'), isTrue);
        expect(json.containsKey('updated_at'), isTrue);
        expect(json.containsKey('initial_run_id'), isFalse);
        expect(json.containsKey('name'), isFalse);
        expect(json.containsKey('description'), isFalse);
        expect(json.containsKey('metadata'), isFalse);
      });
    });

    test('roundtrip serialization', () {
      final createdAt = DateTime.utc(2025);
      final updatedAt = DateTime.utc(2025, 1, 2);
      final original = ThreadInfo(
        id: 'thread-1',
        roomId: 'room-1',
        initialRunId: 'run-1',
        name: 'Test Thread',
        description: 'A test thread',
        createdAt: createdAt,
        updatedAt: updatedAt,
        metadata: const {'key': 'value'},
      );

      final json = original.toJson();
      final restored = ThreadInfo.fromJson(json);

      expect(restored.id, equals(original.id));
      expect(restored.roomId, equals(original.roomId));
      expect(restored.initialRunId, equals(original.initialRunId));
      expect(restored.name, equals(original.name));
      expect(restored.description, equals(original.description));
      expect(restored.createdAt, equals(original.createdAt));
      expect(restored.updatedAt, equals(original.updatedAt));
      expect(restored.metadata, equals(original.metadata));
    });

    group('copyWith', () {
      test('creates modified copy', () {
        final thread = ThreadInfo(
          id: 'thread-1',
          roomId: 'room-1',
          createdAt: DateTime(2025),
          updatedAt: DateTime(2025),
        );
        final modified = thread.copyWith(name: 'New Name');

        expect(modified.id, equals('thread-1'));
        expect(modified.roomId, equals('room-1'));
        expect(modified.name, equals('New Name'));
        expect(thread.name, equals(''));
      });

      test('creates copy with all fields modified', () {
        final thread = ThreadInfo(
          id: 'thread-1',
          roomId: 'room-1',
          createdAt: DateTime(2025),
          updatedAt: DateTime(2025),
        );
        final newCreated = DateTime(2025, 6);
        final newUpdated = DateTime(2025, 6, 2);
        final modified = thread.copyWith(
          id: 'thread-2',
          roomId: 'room-2',
          initialRunId: 'run-1',
          name: 'New Name',
          description: 'New description',
          createdAt: newCreated,
          updatedAt: newUpdated,
          metadata: {'new': 'data'},
        );

        expect(modified.id, equals('thread-2'));
        expect(modified.roomId, equals('room-2'));
        expect(modified.initialRunId, equals('run-1'));
        expect(modified.name, equals('New Name'));
        expect(modified.description, equals('New description'));
        expect(modified.createdAt, equals(newCreated));
        expect(modified.updatedAt, equals(newUpdated));
        expect(modified.metadata, equals({'new': 'data'}));
      });

      test('creates identical copy when no parameters passed', () {
        final createdAt = DateTime(2025);
        final updatedAt = DateTime(2025, 1, 2);
        final thread = ThreadInfo(
          id: 'thread-1',
          roomId: 'room-1',
          initialRunId: 'run-1',
          name: 'Test Thread',
          description: 'A test thread',
          createdAt: createdAt,
          updatedAt: updatedAt,
          metadata: const {'key': 'value'},
        );

        final copy = thread.copyWith();

        expect(copy.id, equals(thread.id));
        expect(copy.roomId, equals(thread.roomId));
        expect(copy.initialRunId, equals(thread.initialRunId));
        expect(copy.name, equals(thread.name));
        expect(copy.description, equals(thread.description));
        expect(copy.createdAt, equals(thread.createdAt));
        expect(copy.updatedAt, equals(thread.updatedAt));
        expect(copy.metadata, equals(thread.metadata));
      });
    });

    group('equality', () {
      test('equal based on id and roomId', () {
        final thread1 = ThreadInfo(
          id: 'thread-1',
          roomId: 'room-1',
          name: 'Thread 1',
          createdAt: DateTime(2025),
          updatedAt: DateTime(2025),
        );
        final thread2 = ThreadInfo(
          id: 'thread-1',
          roomId: 'room-1',
          name: 'Thread 2',
          createdAt: DateTime(2025),
          updatedAt: DateTime(2025),
        );
        final thread3 = ThreadInfo(
          id: 'thread-1',
          roomId: 'room-2',
          name: 'Thread 1',
          createdAt: DateTime(2025),
          updatedAt: DateTime(2025),
        );
        final thread4 = ThreadInfo(
          id: 'thread-2',
          roomId: 'room-1',
          name: 'Thread 1',
          createdAt: DateTime(2025),
          updatedAt: DateTime(2025),
        );

        expect(thread1, equals(thread2));
        expect(thread1, isNot(equals(thread3)));
        expect(thread1, isNot(equals(thread4)));
      });

      test('identical returns true', () {
        final thread = ThreadInfo(
          id: 'thread-1',
          roomId: 'room-1',
          createdAt: DateTime(2025),
          updatedAt: DateTime(2025),
        );
        expect(thread == thread, isTrue);
      });
    });

    test('hashCode based on id and roomId', () {
      final thread1 = ThreadInfo(
        id: 'thread-1',
        roomId: 'room-1',
        name: 'Thread 1',
        createdAt: DateTime(2025),
        updatedAt: DateTime(2025),
      );
      final thread2 = ThreadInfo(
        id: 'thread-1',
        roomId: 'room-1',
        name: 'Thread 2',
        createdAt: DateTime(2025),
        updatedAt: DateTime(2025),
      );

      expect(thread1.hashCode, equals(thread2.hashCode));
    });

    test('toString includes id, roomId, and name', () {
      final thread = ThreadInfo(
        id: 'thread-1',
        roomId: 'room-1',
        name: 'Test Thread',
        createdAt: DateTime(2025),
        updatedAt: DateTime(2025),
      );

      final str = thread.toString();

      expect(str, contains('thread-1'));
      expect(str, contains('room-1'));
      expect(str, contains('Test Thread'));
    });
  });
}
