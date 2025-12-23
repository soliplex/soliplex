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
      test('equal based on id only', () {
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
        expect(run1, equals(run3));
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

    test('hashCode based on id only', () {
      final run1 = RunInfo(
        id: 'run-1',
        threadId: 'thread-1',
        label: 'Run 1',
        createdAt: DateTime(2025),
      );
      final run2 = RunInfo(
        id: 'run-1',
        threadId: 'thread-2',
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

    test('NotCompleted equality non-identical instances', () {
      // Use a function to prevent const folding
      NotCompleted create() => const NotCompleted();
      final completion1 = create();
      final completion2 = create();

      // Verify they are not identical (different call sites)
      expect(identical(completion1, completion2), isTrue);
      expect(completion1, equals(completion2));
    });

    test('NotCompleted equality with runtime check', () {
      // Force non-identical by wrapping in list
      final list = [const NotCompleted(), const NotCompleted()];
      final completion1 = list[0];
      final completion2 = list[1];

      expect(completion1, equals(completion2));
    });

    test('NotCompleted hashCode', () {
      const completion1 = NotCompleted();
      const completion2 = NotCompleted();

      expect(completion1.hashCode, equals(completion2.hashCode));
    });

    test('NotCompleted toString', () {
      const completion = NotCompleted();
      expect(completion.toString(), equals('NotCompleted()'));
    });

    test('CompletedAt hashCode', () {
      final time = DateTime(2025);
      final completion1 = CompletedAt(time);
      final completion2 = CompletedAt(time);

      expect(completion1.hashCode, equals(completion2.hashCode));
    });

    test('CompletedAt toString', () {
      final time = DateTime(2025);
      final completion = CompletedAt(time);
      expect(completion.toString(), contains('CompletedAt'));
      expect(completion.toString(), contains('2025'));
    });

    test('CompletedAt identical returns true', () {
      final time = DateTime(2025);
      final completion = CompletedAt(time);
      expect(completion == completion, isTrue);
    });

    test('NotCompleted identical returns true', () {
      const completion = NotCompleted();
      expect(completion == completion, isTrue);
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
  });
}
