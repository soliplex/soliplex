import 'package:soliplex_client/src/api/mappers.dart';
import 'package:soliplex_client/src/domain/room.dart';
import 'package:soliplex_client/src/domain/run_info.dart';
import 'package:soliplex_client/src/domain/thread_info.dart';
import 'package:test/test.dart';

void main() {
  group('Room mappers', () {
    group('roomFromJson', () {
      test('parses correctly with all fields', () {
        final json = <String, dynamic>{
          'id': 'room-1',
          'name': 'Test Room',
          'description': 'A test room',
          'metadata': {'key': 'value'},
        };

        final room = roomFromJson(json);

        expect(room.id, equals('room-1'));
        expect(room.name, equals('Test Room'));
        expect(room.description, equals('A test room'));
        expect(room.metadata, equals({'key': 'value'}));
      });

      test('parses correctly with only required fields', () {
        final json = <String, dynamic>{
          'id': 'room-1',
          'name': 'Test Room',
        };

        final room = roomFromJson(json);

        expect(room.id, equals('room-1'));
        expect(room.name, equals('Test Room'));
        expect(room.description, equals(''));
        expect(room.metadata, equals(const <String, dynamic>{}));
      });

      test('handles null description', () {
        final json = <String, dynamic>{
          'id': 'room-1',
          'name': 'Test Room',
          'description': null,
        };

        final room = roomFromJson(json);

        expect(room.description, equals(''));
      });

      test('handles null metadata', () {
        final json = <String, dynamic>{
          'id': 'room-1',
          'name': 'Test Room',
          'metadata': null,
        };

        final room = roomFromJson(json);

        expect(room.metadata, equals(const <String, dynamic>{}));
      });
    });

    group('roomToJson', () {
      test('serializes correctly with all fields', () {
        const room = Room(
          id: 'room-1',
          name: 'Test Room',
          description: 'A test room',
          metadata: {'key': 'value'},
        );

        final json = roomToJson(room);

        expect(json['id'], equals('room-1'));
        expect(json['name'], equals('Test Room'));
        expect(json['description'], equals('A test room'));
        expect(json['metadata'], equals({'key': 'value'}));
      });

      test('excludes empty fields', () {
        const room = Room(id: 'room-1', name: 'Test Room');

        final json = roomToJson(room);

        expect(json.containsKey('id'), isTrue);
        expect(json.containsKey('name'), isTrue);
        expect(json.containsKey('description'), isFalse);
        expect(json.containsKey('metadata'), isFalse);
      });
    });

    test('roundtrip serialization', () {
      const original = Room(
        id: 'room-1',
        name: 'Test Room',
        description: 'A test room',
        metadata: {'key': 'value'},
      );

      final json = roomToJson(original);
      final restored = roomFromJson(json);

      expect(restored.id, equals(original.id));
      expect(restored.name, equals(original.name));
      expect(restored.description, equals(original.description));
      expect(restored.metadata, equals(original.metadata));
    });
  });

  group('ThreadInfo mappers', () {
    group('threadInfoFromJson', () {
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

        final thread = threadInfoFromJson(json);

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

        final thread = threadInfoFromJson(json);

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

        final thread = threadInfoFromJson(json);

        expect(thread.id, equals('thread-1'));
      });

      test('handles missing room_id', () {
        final json = <String, dynamic>{
          'id': 'thread-1',
        };

        final thread = threadInfoFromJson(json);

        expect(thread.roomId, equals(''));
      });

      test('handles invalid created_at DateTime', () {
        final json = <String, dynamic>{
          'id': 'thread-1',
          'room_id': 'room-1',
          'created_at': 'invalid-date',
        };

        final thread = threadInfoFromJson(json);

        expect(thread.createdAt, isNotNull);
      });

      test('handles invalid updated_at DateTime', () {
        final json = <String, dynamic>{
          'id': 'thread-1',
          'room_id': 'room-1',
          'created_at': '2025-01-01T00:00:00.000Z',
          'updated_at': 'invalid-date',
        };

        final thread = threadInfoFromJson(json);

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

        final thread = threadInfoFromJson(json);

        expect(thread.initialRunId, equals(''));
        expect(thread.name, equals(''));
        expect(thread.description, equals(''));
        expect(thread.metadata, equals(const <String, dynamic>{}));
      });
    });

    group('threadInfoToJson', () {
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

        final json = threadInfoToJson(thread);

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

        final json = threadInfoToJson(thread);

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

      final json = threadInfoToJson(original);
      final restored = threadInfoFromJson(json);

      expect(restored.id, equals(original.id));
      expect(restored.roomId, equals(original.roomId));
      expect(restored.initialRunId, equals(original.initialRunId));
      expect(restored.name, equals(original.name));
      expect(restored.description, equals(original.description));
      expect(restored.createdAt, equals(original.createdAt));
      expect(restored.updatedAt, equals(original.updatedAt));
      expect(restored.metadata, equals(original.metadata));
    });
  });

  group('RunInfo mappers', () {
    group('runInfoFromJson', () {
      test('parses correctly with all fields', () {
        final json = <String, dynamic>{
          'id': 'run-1',
          'thread_id': 'thread-1',
          'label': 'Test Run',
          'created_at': '2025-01-01T00:00:00.000Z',
          'completed_at': '2025-01-02T00:00:00.000Z',
          'status': 'completed',
          'metadata': {'key': 'value'},
        };

        final run = runInfoFromJson(json);

        expect(run.id, equals('run-1'));
        expect(run.threadId, equals('thread-1'));
        expect(run.label, equals('Test Run'));
        expect(run.createdAt, isNotNull);
        expect(run.completion, isA<CompletedAt>());
        expect(run.status, equals(RunStatus.completed));
        expect(run.metadata, equals({'key': 'value'}));
      });

      test('parses correctly with only required fields', () {
        final json = <String, dynamic>{
          'id': 'run-1',
          'thread_id': 'thread-1',
        };

        final run = runInfoFromJson(json);

        expect(run.id, equals('run-1'));
        expect(run.threadId, equals('thread-1'));
        expect(run.label, equals(''));
        expect(run.createdAt, isNotNull);
        expect(run.completion, isA<NotCompleted>());
        expect(run.status, equals(RunStatus.pending));
        expect(run.metadata, equals(const <String, dynamic>{}));
      });

      test('handles run_id field', () {
        final json = <String, dynamic>{
          'run_id': 'run-1',
          'thread_id': 'thread-1',
        };

        final run = runInfoFromJson(json);

        expect(run.id, equals('run-1'));
      });

      test('handles missing thread_id', () {
        final json = <String, dynamic>{
          'id': 'run-1',
        };

        final run = runInfoFromJson(json);

        expect(run.threadId, equals(''));
      });

      test('handles invalid completed_at DateTime', () {
        final json = <String, dynamic>{
          'id': 'run-1',
          'thread_id': 'thread-1',
          'completed_at': 'invalid-date',
        };

        final run = runInfoFromJson(json);

        expect(run.completion, isA<CompletedAt>());
        expect((run.completion as CompletedAt).time, isNotNull);
      });

      test('handles invalid created_at DateTime', () {
        final json = <String, dynamic>{
          'id': 'run-1',
          'thread_id': 'thread-1',
          'created_at': 'invalid-date',
        };

        final run = runInfoFromJson(json);

        expect(run.createdAt, isNotNull);
      });

      test('handles null label', () {
        final json = <String, dynamic>{
          'id': 'run-1',
          'thread_id': 'thread-1',
          'label': null,
        };

        final run = runInfoFromJson(json);

        expect(run.label, equals(''));
      });

      test('handles null metadata', () {
        final json = <String, dynamic>{
          'id': 'run-1',
          'thread_id': 'thread-1',
          'metadata': null,
        };

        final run = runInfoFromJson(json);

        expect(run.metadata, equals(const <String, dynamic>{}));
      });
    });

    group('runInfoToJson', () {
      test('serializes correctly with all fields', () {
        final createdAt = DateTime.utc(2025);
        final completedAt = DateTime.utc(2025, 1, 2);
        final run = RunInfo(
          id: 'run-1',
          threadId: 'thread-1',
          label: 'Test Run',
          createdAt: createdAt,
          completion: CompletedAt(completedAt),
          status: RunStatus.completed,
          metadata: const {'key': 'value'},
        );

        final json = runInfoToJson(run);

        expect(json['id'], equals('run-1'));
        expect(json['thread_id'], equals('thread-1'));
        expect(json['label'], equals('Test Run'));
        expect(json['created_at'], equals('2025-01-01T00:00:00.000Z'));
        expect(json['completed_at'], equals('2025-01-02T00:00:00.000Z'));
        expect(json['status'], equals('completed'));
        expect(json['metadata'], equals({'key': 'value'}));
      });

      test('excludes empty fields', () {
        final run = RunInfo(
          id: 'run-1',
          threadId: 'thread-1',
          createdAt: DateTime.utc(2025),
        );

        final json = runInfoToJson(run);

        expect(json.containsKey('id'), isTrue);
        expect(json.containsKey('thread_id'), isTrue);
        expect(json.containsKey('created_at'), isTrue);
        expect(json.containsKey('status'), isTrue);
        expect(json.containsKey('label'), isFalse);
        expect(json.containsKey('completed_at'), isFalse);
        expect(json.containsKey('metadata'), isFalse);
      });
    });

    test('roundtrip serialization', () {
      final createdAt = DateTime.utc(2025);
      final completedAt = DateTime.utc(2025, 1, 2);
      final original = RunInfo(
        id: 'run-1',
        threadId: 'thread-1',
        label: 'Test Run',
        createdAt: createdAt,
        completion: CompletedAt(completedAt),
        status: RunStatus.completed,
        metadata: const {'key': 'value'},
      );

      final json = runInfoToJson(original);
      final restored = runInfoFromJson(json);

      expect(restored.id, equals(original.id));
      expect(restored.threadId, equals(original.threadId));
      expect(restored.label, equals(original.label));
      expect(restored.createdAt, equals(original.createdAt));
      expect(restored.isCompleted, equals(original.isCompleted));
      expect(restored.status, equals(original.status));
      expect(restored.metadata, equals(original.metadata));
    });
  });

  group('runStatusFromString', () {
    test('parses valid status strings', () {
      expect(runStatusFromString('pending'), equals(RunStatus.pending));
      expect(runStatusFromString('running'), equals(RunStatus.running));
      expect(runStatusFromString('completed'), equals(RunStatus.completed));
      expect(runStatusFromString('failed'), equals(RunStatus.failed));
      expect(runStatusFromString('cancelled'), equals(RunStatus.cancelled));
    });

    test('handles uppercase status strings', () {
      expect(runStatusFromString('PENDING'), equals(RunStatus.pending));
      expect(runStatusFromString('Running'), equals(RunStatus.running));
      expect(runStatusFromString('COMPLETED'), equals(RunStatus.completed));
    });

    test('returns pending for null', () {
      expect(runStatusFromString(null), equals(RunStatus.pending));
    });

    test('returns pending for unknown status', () {
      expect(runStatusFromString('unknown'), equals(RunStatus.pending));
      expect(runStatusFromString('invalid'), equals(RunStatus.pending));
    });
  });
}
