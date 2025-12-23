import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('Room', () {
    test('creates with required fields', () {
      const room = Room(id: 'room-1', name: 'Test Room');

      expect(room.id, equals('room-1'));
      expect(room.name, equals('Test Room'));
      expect(room.description, equals(''));
      expect(room.metadata, equals(const <String, dynamic>{}));
      expect(room.hasDescription, isFalse);
    });

    test('creates with all fields', () {
      const room = Room(
        id: 'room-1',
        name: 'Test Room',
        description: 'A test room',
        metadata: {'key': 'value'},
      );

      expect(room.id, equals('room-1'));
      expect(room.name, equals('Test Room'));
      expect(room.description, equals('A test room'));
      expect(room.metadata, equals({'key': 'value'}));
      expect(room.hasDescription, isTrue);
    });

    group('copyWith', () {
      test('creates modified copy', () {
        const room = Room(id: 'room-1', name: 'Test Room');
        final modified = room.copyWith(name: 'Modified Room');

        expect(modified.id, equals('room-1'));
        expect(modified.name, equals('Modified Room'));
        expect(room.name, equals('Test Room'));
      });

      test('creates copy with all fields modified', () {
        const room = Room(id: 'room-1', name: 'Test Room');
        final modified = room.copyWith(
          id: 'room-2',
          name: 'New Room',
          description: 'New description',
          metadata: {'new': 'data'},
        );

        expect(modified.id, equals('room-2'));
        expect(modified.name, equals('New Room'));
        expect(modified.description, equals('New description'));
        expect(modified.metadata, equals({'new': 'data'}));
      });

      test('creates identical copy when no parameters passed', () {
        const room = Room(
          id: 'room-1',
          name: 'Test Room',
          description: 'A description',
          metadata: {'key': 'value'},
        );
        final copy = room.copyWith();

        expect(copy.id, equals(room.id));
        expect(copy.name, equals(room.name));
        expect(copy.description, equals(room.description));
        expect(copy.metadata, equals(room.metadata));
      });
    });

    group('equality', () {
      test('equal based on id', () {
        const room1 = Room(id: 'room-1', name: 'Room 1');
        const room2 = Room(id: 'room-1', name: 'Room 2');
        const room3 = Room(id: 'room-2', name: 'Room 1');

        expect(room1, equals(room2));
        expect(room1, isNot(equals(room3)));
      });

      test('identical returns true', () {
        const room = Room(id: 'room-1', name: 'Test Room');
        expect(room == room, isTrue);
      });
    });

    test('hashCode based on id', () {
      const room1 = Room(id: 'room-1', name: 'Room 1');
      const room2 = Room(id: 'room-1', name: 'Room 2');

      expect(room1.hashCode, equals(room2.hashCode));
    });

    test('toString includes id and name', () {
      const room = Room(id: 'room-1', name: 'Test Room');

      final str = room.toString();

      expect(str, contains('room-1'));
      expect(str, contains('Test Room'));
    });
  });
}
