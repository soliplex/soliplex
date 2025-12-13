import 'package:soliplex_flutter/client/models/run_info.dart';
import 'package:test/test.dart';

void main() {
  group('RunInfo', () {
    test('creates with required fields', () {
      const run = RunInfo(id: 'run1', threadId: 't1');

      expect(run.id, equals('run1'));
      expect(run.threadId, equals('t1'));
      expect(run.label, isNull);
      expect(run.createdAt, isNull);
      expect(run.completedAt, isNull);
      expect(run.status, equals(RunStatus.pending));
      expect(run.metadata, isNull);
    });

    test('creates with all fields', () {
      final createdAt = DateTime(2024, 1, 1);
      final completedAt = DateTime(2024, 1, 2);
      final run = RunInfo(
        id: 'run1',
        threadId: 't1',
        label: 'Test Run',
        createdAt: createdAt,
        completedAt: completedAt,
        status: RunStatus.completed,
        metadata: {'key': 'value'},
      );

      expect(run.id, equals('run1'));
      expect(run.threadId, equals('t1'));
      expect(run.label, equals('Test Run'));
      expect(run.createdAt, equals(createdAt));
      expect(run.completedAt, equals(completedAt));
      expect(run.status, equals(RunStatus.completed));
      expect(run.metadata, equals({'key': 'value'}));
    });

    test('fromJson parses with id field', () {
      final run = RunInfo.fromJson({
        'id': 'run1',
        'thread_id': 't1',
        'label': 'Test',
      });

      expect(run.id, equals('run1'));
      expect(run.threadId, equals('t1'));
      expect(run.label, equals('Test'));
    });

    test('fromJson parses with run_id field', () {
      final run = RunInfo.fromJson({
        'run_id': 'run2',
        'thread_id': 't1',
      });

      expect(run.id, equals('run2'));
    });

    test('fromJson parses dates', () {
      final run = RunInfo.fromJson({
        'id': 'run1',
        'thread_id': 't1',
        'created_at': '2024-01-01T00:00:00.000Z',
        'completed_at': '2024-01-02T00:00:00.000Z',
      });

      expect(run.createdAt, isNotNull);
      expect(run.completedAt, isNotNull);
    });

    test('fromJson handles missing thread_id', () {
      final run = RunInfo.fromJson({'id': 'run1'});

      expect(run.threadId, equals(''));
    });

    test('fromJson parses status', () {
      final runRunning = RunInfo.fromJson({
        'id': 'run1',
        'thread_id': 't1',
        'status': 'running',
      });
      final runCompleted = RunInfo.fromJson({
        'id': 'run2',
        'thread_id': 't1',
        'status': 'completed',
      });
      final runFailed = RunInfo.fromJson({
        'id': 'run3',
        'thread_id': 't1',
        'status': 'failed',
      });
      final runCancelled = RunInfo.fromJson({
        'id': 'run4',
        'thread_id': 't1',
        'status': 'cancelled',
      });

      expect(runRunning.status, equals(RunStatus.running));
      expect(runCompleted.status, equals(RunStatus.completed));
      expect(runFailed.status, equals(RunStatus.failed));
      expect(runCancelled.status, equals(RunStatus.cancelled));
    });

    test('toJson serializes correctly', () {
      final createdAt = DateTime.utc(2024, 1, 1);
      final run = RunInfo(
        id: 'run1',
        threadId: 't1',
        label: 'Test',
        createdAt: createdAt,
        status: RunStatus.running,
        metadata: {'key': 'value'},
      );

      final json = run.toJson();

      expect(json['id'], equals('run1'));
      expect(json['thread_id'], equals('t1'));
      expect(json['label'], equals('Test'));
      expect(json['created_at'], equals('2024-01-01T00:00:00.000Z'));
      expect(json['status'], equals('running'));
      expect(json['metadata'], equals({'key': 'value'}));
    });

    test('toJson excludes null fields', () {
      const run = RunInfo(id: 'run1', threadId: 't1');

      final json = run.toJson();

      expect(json.containsKey('label'), isFalse);
      expect(json.containsKey('created_at'), isFalse);
      expect(json.containsKey('completed_at'), isFalse);
      expect(json.containsKey('metadata'), isFalse);
      expect(json.containsKey('status'), isTrue); // status always included
    });

    test('copyWith creates modified copy', () {
      const original = RunInfo(id: 'run1', threadId: 't1');

      final copy = original.copyWith(
        label: 'New Label',
        status: RunStatus.completed,
      );

      expect(copy.id, equals('run1'));
      expect(copy.threadId, equals('t1'));
      expect(copy.label, equals('New Label'));
      expect(copy.status, equals(RunStatus.completed));
    });

    test('copyWith preserves original when no changes', () {
      const original = RunInfo(
        id: 'run1',
        threadId: 't1',
        label: 'Test',
      );

      final copy = original.copyWith();

      expect(copy.id, equals(original.id));
      expect(copy.threadId, equals(original.threadId));
      expect(copy.label, equals(original.label));
    });

    test('equality based on id and threadId', () {
      const run1 = RunInfo(id: 'run1', threadId: 't1', label: 'Label1');
      const run2 = RunInfo(id: 'run1', threadId: 't1', label: 'Label2');
      const run3 = RunInfo(id: 'run2', threadId: 't1');

      expect(run1, equals(run2));
      expect(run1, isNot(equals(run3)));
    });

    test('hashCode based on id and threadId', () {
      const run1 = RunInfo(id: 'run1', threadId: 't1', label: 'Label1');
      const run2 = RunInfo(id: 'run1', threadId: 't1', label: 'Label2');

      expect(run1.hashCode, equals(run2.hashCode));
    });

    test('toString includes key fields', () {
      const run = RunInfo(
        id: 'run1',
        threadId: 't1',
        status: RunStatus.running,
      );

      final str = run.toString();

      expect(str, contains('run1'));
      expect(str, contains('t1'));
      expect(str, contains('running'));
    });
  });

  group('RunStatus', () {
    test('fromString parses valid statuses', () {
      expect(RunStatus.fromString('pending'), equals(RunStatus.pending));
      expect(RunStatus.fromString('running'), equals(RunStatus.running));
      expect(RunStatus.fromString('completed'), equals(RunStatus.completed));
      expect(RunStatus.fromString('failed'), equals(RunStatus.failed));
      expect(RunStatus.fromString('cancelled'), equals(RunStatus.cancelled));
    });

    test('fromString is case insensitive', () {
      expect(RunStatus.fromString('RUNNING'), equals(RunStatus.running));
      expect(RunStatus.fromString('Completed'), equals(RunStatus.completed));
    });

    test('fromString returns pending for null', () {
      expect(RunStatus.fromString(null), equals(RunStatus.pending));
    });

    test('fromString returns pending for unknown value', () {
      expect(RunStatus.fromString('unknown'), equals(RunStatus.pending));
    });
  });
}
