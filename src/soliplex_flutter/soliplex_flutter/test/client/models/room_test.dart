import 'package:soliplex_flutter/client/models/room.dart';
import 'package:test/test.dart';

void main() {
  group('Room', () {
    test('creates with required fields', () {
      const room = Room(id: 'room-1', name: 'Test Room');

      expect(room.id, 'room-1');
      expect(room.name, 'Test Room');
      expect(room.description, isNull);
      expect(room.metadata, isNull);
    });

    test('creates with all fields', () {
      const room = Room(
        id: 'room-1',
        name: 'Test Room',
        description: 'A test room',
        metadata: {'key': 'value'},
      );

      expect(room.id, 'room-1');
      expect(room.name, 'Test Room');
      expect(room.description, 'A test room');
      expect(room.metadata, {'key': 'value'});
    });

    test('fromJson parses correctly', () {
      final json = {
        'id': 'room-1',
        'name': 'Test Room',
        'description': 'A test room',
        'metadata': {'key': 'value'},
      };

      final room = Room.fromJson(json);

      expect(room.id, 'room-1');
      expect(room.name, 'Test Room');
      expect(room.description, 'A test room');
      expect(room.metadata, {'key': 'value'});
    });

    test('toJson serializes correctly', () {
      const room = Room(
        id: 'room-1',
        name: 'Test Room',
        description: 'A test room',
      );

      final json = room.toJson();

      expect(json['id'], 'room-1');
      expect(json['name'], 'Test Room');
      expect(json['description'], 'A test room');
    });

    test('toJson excludes null fields', () {
      const room = Room(id: 'room-1', name: 'Test Room');

      final json = room.toJson();

      expect(json.containsKey('description'), isFalse);
      expect(json.containsKey('metadata'), isFalse);
    });

    test('copyWith creates modified copy', () {
      const room = Room(id: 'room-1', name: 'Test Room');
      final modified = room.copyWith(name: 'Modified Room');

      expect(modified.id, 'room-1');
      expect(modified.name, 'Modified Room');
      expect(room.name, 'Test Room'); // Original unchanged
    });

    test('equality based on id', () {
      const room1 = Room(id: 'room-1', name: 'Room 1');
      const room2 = Room(id: 'room-1', name: 'Room 2');
      const room3 = Room(id: 'room-2', name: 'Room 1');

      expect(room1, equals(room2));
      expect(room1, isNot(equals(room3)));
    });

    test('hashCode based on id', () {
      const room1 = Room(id: 'room-1', name: 'Room 1');
      const room2 = Room(id: 'room-1', name: 'Room 2');

      expect(room1.hashCode, equals(room2.hashCode));
    });
  });
}
