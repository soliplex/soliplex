import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('RunInfo', () {
    test('creates with required fields', () {
      const run = RunInfo(id: 'run-1', threadId: 'thread-1');

      expect(run.id, equals('run-1'));
      expect(run.threadId, equals('thread-1'));
      expect(run.label, isNull);
      expect(run.createdAt, isNull);
      expect(run.completedAt, isNull);
      expect(run.status, equals(RunStatus.pending));
      expect(run.metadata, isNull);
    });

    test('creates with all fields', () {
      final createdAt = DateTime(2025);
      final completedAt = DateTime(2025, 1, 2);
      final run = RunInfo(
        id: 'run-1',
        threadId: 'thread-1',
        label: 'Test Run',
        createdAt: createdAt,
        completedAt: completedAt,
        status: RunStatus.completed,
        metadata: const {'key': 'value'},
      );

      expect(run.id, equals('run-1'));
      expect(run.threadId, equals('thread-1'));
      expect(run.label, equals('Test Run'));
      expect(run.createdAt, equals(createdAt));
      expect(run.completedAt, equals(completedAt));
      expect(run.status, equals(RunStatus.completed));
      expect(run.metadata, equals({'key': 'value'}));
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
        expect(run.completedAt, isNotNull);
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
        expect(run.label, isNull);
        expect(run.createdAt, isNull);
        expect(run.completedAt, isNull);
        expect(run.status, equals(RunStatus.pending));
        expect(run.metadata, isNull);
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
          completedAt: completedAt,
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

      test('excludes null fields except status', () {
        const run = RunInfo(id: 'run-1', threadId: 'thread-1');

        final json = run.toJson();

        expect(json.containsKey('id'), isTrue);
        expect(json.containsKey('thread_id'), isTrue);
        expect(json.containsKey('status'), isTrue);
        expect(json.containsKey('label'), isFalse);
        expect(json.containsKey('created_at'), isFalse);
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
        completedAt: completedAt,
        status: RunStatus.completed,
        metadata: const {'key': 'value'},
      );

      final json = original.toJson();
      final restored = RunInfo.fromJson(json);

      expect(restored.id, equals(original.id));
      expect(restored.threadId, equals(original.threadId));
      expect(restored.label, equals(original.label));
      expect(restored.createdAt, equals(original.createdAt));
      expect(restored.completedAt, equals(original.completedAt));
      expect(restored.status, equals(original.status));
      expect(restored.metadata, equals(original.metadata));
    });

    group('copyWith', () {
      test('creates modified copy', () {
        const run = RunInfo(id: 'run-1', threadId: 'thread-1');
        final modified = run.copyWith(status: RunStatus.running);

        expect(modified.id, equals('run-1'));
        expect(modified.threadId, equals('thread-1'));
        expect(modified.status, equals(RunStatus.running));
        expect(run.status, equals(RunStatus.pending));
      });

      test('creates copy with all fields modified', () {
        const run = RunInfo(id: 'run-1', threadId: 'thread-1');
        final newCreated = DateTime(2025, 6);
        final newCompleted = DateTime(2025, 6, 2);
        final modified = run.copyWith(
          id: 'run-2',
          threadId: 'thread-2',
          label: 'New Label',
          createdAt: newCreated,
          completedAt: newCompleted,
          status: RunStatus.completed,
          metadata: {'new': 'data'},
        );

        expect(modified.id, equals('run-2'));
        expect(modified.threadId, equals('thread-2'));
        expect(modified.label, equals('New Label'));
        expect(modified.createdAt, equals(newCreated));
        expect(modified.completedAt, equals(newCompleted));
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
          completedAt: completedAt,
          status: RunStatus.completed,
          metadata: const {'key': 'value'},
        );

        final copy = run.copyWith();

        expect(copy.id, equals(run.id));
        expect(copy.threadId, equals(run.threadId));
        expect(copy.label, equals(run.label));
        expect(copy.createdAt, equals(run.createdAt));
        expect(copy.completedAt, equals(run.completedAt));
        expect(copy.status, equals(run.status));
        expect(copy.metadata, equals(run.metadata));
      });
    });

    group('equality', () {
      test('equal based on id and threadId', () {
        const run1 = RunInfo(
          id: 'run-1',
          threadId: 'thread-1',
          label: 'Run 1',
        );
        const run2 = RunInfo(
          id: 'run-1',
          threadId: 'thread-1',
          label: 'Run 2',
        );
        const run3 = RunInfo(
          id: 'run-1',
          threadId: 'thread-2',
          label: 'Run 1',
        );
        const run4 = RunInfo(
          id: 'run-2',
          threadId: 'thread-1',
          label: 'Run 1',
        );

        expect(run1, equals(run2));
        expect(run1, isNot(equals(run3)));
        expect(run1, isNot(equals(run4)));
      });

      test('identical returns true', () {
        const run = RunInfo(id: 'run-1', threadId: 'thread-1');
        expect(run == run, isTrue);
      });
    });

    test('hashCode based on id and threadId', () {
      const run1 = RunInfo(
        id: 'run-1',
        threadId: 'thread-1',
        label: 'Run 1',
      );
      const run2 = RunInfo(
        id: 'run-1',
        threadId: 'thread-1',
        label: 'Run 2',
      );

      expect(run1.hashCode, equals(run2.hashCode));
    });

    test('toString includes id, threadId, and status', () {
      const run = RunInfo(
        id: 'run-1',
        threadId: 'thread-1',
        status: RunStatus.running,
      );

      final str = run.toString();

      expect(str, contains('run-1'));
      expect(str, contains('thread-1'));
      expect(str, contains('running'));
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
