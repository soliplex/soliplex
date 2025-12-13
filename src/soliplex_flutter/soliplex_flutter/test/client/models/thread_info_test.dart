import 'package:soliplex_flutter/client/models/thread_info.dart';
import 'package:test/test.dart';

void main() {
  group('ThreadInfo', () {
    test('creates with required fields', () {
      const thread = ThreadInfo(id: 't1', roomId: 'r1');

      expect(thread.id, equals('t1'));
      expect(thread.roomId, equals('r1'));
      expect(thread.name, isNull);
      expect(thread.description, isNull);
      expect(thread.createdAt, isNull);
      expect(thread.updatedAt, isNull);
      expect(thread.metadata, isNull);
    });

    test('creates with all fields', () {
      final createdAt = DateTime(2024, 1, 1);
      final updatedAt = DateTime(2024, 1, 2);
      final thread = ThreadInfo(
        id: 't1',
        roomId: 'r1',
        name: 'Test Thread',
        description: 'A test thread',
        createdAt: createdAt,
        updatedAt: updatedAt,
        metadata: {'key': 'value'},
      );

      expect(thread.id, equals('t1'));
      expect(thread.roomId, equals('r1'));
      expect(thread.name, equals('Test Thread'));
      expect(thread.description, equals('A test thread'));
      expect(thread.createdAt, equals(createdAt));
      expect(thread.updatedAt, equals(updatedAt));
      expect(thread.metadata, equals({'key': 'value'}));
    });

    test('fromJson parses with id field', () {
      final thread = ThreadInfo.fromJson({
        'id': 't1',
        'room_id': 'r1',
        'name': 'Test',
      });

      expect(thread.id, equals('t1'));
      expect(thread.roomId, equals('r1'));
      expect(thread.name, equals('Test'));
    });

    test('fromJson parses with thread_id field', () {
      final thread = ThreadInfo.fromJson({
        'thread_id': 't2',
        'room_id': 'r1',
      });

      expect(thread.id, equals('t2'));
    });

    test('fromJson parses dates', () {
      final thread = ThreadInfo.fromJson({
        'id': 't1',
        'room_id': 'r1',
        'created_at': '2024-01-01T00:00:00.000Z',
        'updated_at': '2024-01-02T00:00:00.000Z',
      });

      expect(thread.createdAt, isNotNull);
      expect(thread.updatedAt, isNotNull);
    });

    test('fromJson handles missing room_id', () {
      final thread = ThreadInfo.fromJson({'id': 't1'});

      expect(thread.roomId, equals(''));
    });

    test('fromJson parses metadata', () {
      final thread = ThreadInfo.fromJson({
        'id': 't1',
        'room_id': 'r1',
        'metadata': {'key': 'value'},
      });

      expect(thread.metadata, equals({'key': 'value'}));
    });

    test('toJson serializes correctly', () {
      final createdAt = DateTime.utc(2024, 1, 1);
      final thread = ThreadInfo(
        id: 't1',
        roomId: 'r1',
        name: 'Test',
        description: 'Desc',
        createdAt: createdAt,
        metadata: {'key': 'value'},
      );

      final json = thread.toJson();

      expect(json['id'], equals('t1'));
      expect(json['room_id'], equals('r1'));
      expect(json['name'], equals('Test'));
      expect(json['description'], equals('Desc'));
      expect(json['created_at'], equals('2024-01-01T00:00:00.000Z'));
      expect(json['metadata'], equals({'key': 'value'}));
    });

    test('toJson excludes null fields', () {
      const thread = ThreadInfo(id: 't1', roomId: 'r1');

      final json = thread.toJson();

      expect(json.containsKey('name'), isFalse);
      expect(json.containsKey('description'), isFalse);
      expect(json.containsKey('created_at'), isFalse);
      expect(json.containsKey('updated_at'), isFalse);
      expect(json.containsKey('metadata'), isFalse);
    });

    test('copyWith creates modified copy', () {
      const original = ThreadInfo(id: 't1', roomId: 'r1', name: 'Original');

      final copy = original.copyWith(name: 'Modified');

      expect(copy.id, equals('t1'));
      expect(copy.roomId, equals('r1'));
      expect(copy.name, equals('Modified'));
    });

    test('copyWith preserves original when no changes', () {
      const original = ThreadInfo(id: 't1', roomId: 'r1', name: 'Test');

      final copy = original.copyWith();

      expect(copy.id, equals(original.id));
      expect(copy.roomId, equals(original.roomId));
      expect(copy.name, equals(original.name));
    });

    test('equality based on id and roomId', () {
      const thread1 = ThreadInfo(id: 't1', roomId: 'r1', name: 'Name1');
      const thread2 = ThreadInfo(id: 't1', roomId: 'r1', name: 'Name2');
      const thread3 = ThreadInfo(id: 't2', roomId: 'r1');

      expect(thread1, equals(thread2));
      expect(thread1, isNot(equals(thread3)));
    });

    test('hashCode based on id and roomId', () {
      const thread1 = ThreadInfo(id: 't1', roomId: 'r1', name: 'Name1');
      const thread2 = ThreadInfo(id: 't1', roomId: 'r1', name: 'Name2');

      expect(thread1.hashCode, equals(thread2.hashCode));
    });

    test('toString includes key fields', () {
      const thread = ThreadInfo(id: 't1', roomId: 'r1', name: 'Test');

      final str = thread.toString();

      expect(str, contains('t1'));
      expect(str, contains('r1'));
      expect(str, contains('Test'));
    });
  });
}
