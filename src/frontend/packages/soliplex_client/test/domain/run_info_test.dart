import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('RunInfo', () {
    test('creates with required fields', () {
      final createdAt = DateTime(2025);
      final run = RunInfo(
        id: 'run-1',
        threadId: 'thread-1',
        createdAt: createdAt,
      );

      expect(run.id, equals('run-1'));
      expect(run.threadId, equals('thread-1'));
      expect(run.label, equals(''));
      expect(run.createdAt, equals(createdAt));
      expect(run.completion, isA<NotCompleted>());
      expect(run.isCompleted, isFalse);
      expect(run.status, equals(RunStatus.pending));
      expect(run.metadata, equals(const <String, dynamic>{}));
      expect(run.hasLabel, isFalse);
    });

    test('creates with all fields', () {
      final createdAt = DateTime(2025);
      final completedAt = DateTime(2025, 1, 2);
      final run = RunInfo(
        id: 'run-1',
        threadId: 'thread-1',
        label: 'Test Run',
        createdAt: createdAt,
        completion: CompletedAt(completedAt),
        status: RunStatus.completed,
        metadata: const {'key': 'value'},
      );

      expect(run.id, equals('run-1'));
      expect(run.threadId, equals('thread-1'));
      expect(run.label, equals('Test Run'));
      expect(run.createdAt, equals(createdAt));
      expect(run.completion, isA<CompletedAt>());
      expect((run.completion as CompletedAt).time, equals(completedAt));
      expect(run.isCompleted, isTrue);
      expect(run.status, equals(RunStatus.completed));
      expect(run.metadata, equals({'key': 'value'}));
      expect(run.hasLabel, isTrue);
    });

    group('fromJson', () {
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

        final run = RunInfo.fromJson(json);

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

        final run = RunInfo.fromJson(json);

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

        final run = RunInfo.fromJson(json);

        expect(run.id, equals('run-1'));
      });

      test('handles missing thread_id', () {
        final json = <String, dynamic>{
          'id': 'run-1',
        };

        final run = RunInfo.fromJson(json);

        expect(run.threadId, equals(''));
      });
    });

    group('toJson', () {
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

        final json = run.toJson();

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

        final json = run.toJson();

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

      final json = original.toJson();
      final restored = RunInfo.fromJson(json);

      expect(restored.id, equals(original.id));
      expect(restored.threadId, equals(original.threadId));
      expect(restored.label, equals(original.label));
      expect(restored.createdAt, equals(original.createdAt));
      expect(restored.isCompleted, equals(original.isCompleted));
      expect(restored.status, equals(original.status));
      expect(restored.metadata, equals(original.metadata));
    });

    group('copyWith', () {
      test('creates modified copy', () {
        final run = RunInfo(
          id: 'run-1',
          threadId: 'thread-1',
          createdAt: DateTime(2025),
        );
        final modified = run.copyWith(status: RunStatus.running);

        expect(modified.id, equals('run-1'));
        expect(modified.threadId, equals('thread-1'));
        expect(modified.status, equals(RunStatus.running));
        expect(run.status, equals(RunStatus.pending));
      });

      test('creates copy with all fields modified', () {
        final run = RunInfo(
          id: 'run-1',
          threadId: 'thread-1',
          createdAt: DateTime(2025),
        );
        final newCreated = DateTime(2025, 6);
        final newCompleted = DateTime(2025, 6, 2);
        final modified = run.copyWith(
          id: 'run-2',
          threadId: 'thread-2',
          label: 'New Label',
          createdAt: newCreated,
          completion: CompletedAt(newCompleted),
          status: RunStatus.completed,
          metadata: {'new': 'data'},
        );

        expect(modified.id, equals('run-2'));
        expect(modified.threadId, equals('thread-2'));
        expect(modified.label, equals('New Label'));
        expect(modified.createdAt, equals(newCreated));
        expect(modified.isCompleted, isTrue);
        expect((modified.completion as CompletedAt).time, equals(newCompleted));
        expect(modified.status, equals(RunStatus.completed));
        expect(modified.metadata, equals({'new': 'data'}));
      });

      test('creates identical copy when no parameters passed', () {
        final createdAt = DateTime(2025);
        final completedAt = DateTime(2025, 1, 2);
        final run = RunInfo(
          id: 'run-1',
          threadId: 'thread-1',
          label: 'Test Run',
          createdAt: createdAt,
          completion: CompletedAt(completedAt),
          status: RunStatus.completed,
          metadata: const {'key': 'value'},
        );

        final copy = run.copyWith();

        expect(copy.id, equals(run.id));
        expect(copy.threadId, equals(run.threadId));
        expect(copy.label, equals(run.label));
        expect(copy.createdAt, equals(run.createdAt));
        expect(copy.isCompleted, equals(run.isCompleted));
        expect(copy.status, equals(run.status));
        expect(copy.metadata, equals(run.metadata));
      });
    });

    group('equality', () {
      test('equal based on id and threadId', () {
        final run1 = RunInfo(
          id: 'run-1',
          threadId: 'thread-1',
          label: 'Run 1',
          createdAt: DateTime(2025),
        );
        final run2 = RunInfo(
          id: 'run-1',
          threadId: 'thread-1',
          label: 'Run 2',
          createdAt: DateTime(2025),
        );
        final run3 = RunInfo(
          id: 'run-1',
          threadId: 'thread-2',
          label: 'Run 1',
          createdAt: DateTime(2025),
        );
        final run4 = RunInfo(
          id: 'run-2',
          threadId: 'thread-1',
          label: 'Run 1',
          createdAt: DateTime(2025),
        );

        expect(run1, equals(run2));
        expect(run1, isNot(equals(run3)));
        expect(run1, isNot(equals(run4)));
      });

      test('identical returns true', () {
        final run = RunInfo(
          id: 'run-1',
          threadId: 'thread-1',
          createdAt: DateTime(2025),
        );
        expect(run == run, isTrue);
      });
    });

    test('hashCode based on id and threadId', () {
      final run1 = RunInfo(
        id: 'run-1',
        threadId: 'thread-1',
        label: 'Run 1',
        createdAt: DateTime(2025),
      );
      final run2 = RunInfo(
        id: 'run-1',
        threadId: 'thread-1',
        label: 'Run 2',
        createdAt: DateTime(2025),
      );

      expect(run1.hashCode, equals(run2.hashCode));
    });

    test('toString includes id, threadId, and status', () {
      final run = RunInfo(
        id: 'run-1',
        threadId: 'thread-1',
        status: RunStatus.running,
        createdAt: DateTime(2025),
      );

      final str = run.toString();

      expect(str, contains('run-1'));
      expect(str, contains('thread-1'));
      expect(str, contains('running'));
    });
  });

  group('CompletionTime', () {
    test('NotCompleted is default', () {
      const completion = NotCompleted();
      expect(completion, isA<CompletionTime>());
    });

    test('CompletedAt contains time', () {
      final time = DateTime(2025);
      final completion = CompletedAt(time);
      expect(completion.time, equals(time));
    });

    test('CompletedAt equality', () {
      final time1 = DateTime(2025);
      final time2 = DateTime(2025);
      final time3 = DateTime(2025, 2);

      final completion1 = CompletedAt(time1);
      final completion2 = CompletedAt(time2);
      final completion3 = CompletedAt(time3);

      expect(completion1, equals(completion2));
      expect(completion1, isNot(equals(completion3)));
    });

    test('NotCompleted equality', () {
      const completion1 = NotCompleted();
      const completion2 = NotCompleted();

      expect(completion1, equals(completion2));
    });
  });

  group('RunStatus', () {
    test('has expected values', () {
      expect(RunStatus.values, contains(RunStatus.pending));
      expect(RunStatus.values, contains(RunStatus.running));
      expect(RunStatus.values, contains(RunStatus.completed));
      expect(RunStatus.values, contains(RunStatus.failed));
      expect(RunStatus.values, contains(RunStatus.cancelled));
      expect(RunStatus.values, hasLength(5));
    });

    group('fromString', () {
      test('parses valid status strings', () {
        expect(RunStatus.fromString('pending'), equals(RunStatus.pending));
        expect(RunStatus.fromString('running'), equals(RunStatus.running));
        expect(RunStatus.fromString('completed'), equals(RunStatus.completed));
        expect(RunStatus.fromString('failed'), equals(RunStatus.failed));
        expect(RunStatus.fromString('cancelled'), equals(RunStatus.cancelled));
      });

      test('handles uppercase status strings', () {
        expect(RunStatus.fromString('PENDING'), equals(RunStatus.pending));
        expect(RunStatus.fromString('Running'), equals(RunStatus.running));
        expect(RunStatus.fromString('COMPLETED'), equals(RunStatus.completed));
      });

      test('returns pending for null', () {
        expect(RunStatus.fromString(null), equals(RunStatus.pending));
      });

      test('returns pending for unknown status', () {
        expect(RunStatus.fromString('unknown'), equals(RunStatus.pending));
        expect(RunStatus.fromString('invalid'), equals(RunStatus.pending));
      });
    });
  });
}
