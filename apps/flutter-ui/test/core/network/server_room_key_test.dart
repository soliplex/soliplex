import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/core/network/server_room_key.dart';

void main() {
  group('ServerRoomKey', () {
    group('constructor', () {
      test('creates key with serverId and roomId', () {
        const key = ServerRoomKey(serverId: 'server1', roomId: 'room1');

        expect(key.serverId, equals('server1'));
        expect(key.roomId, equals('room1'));
      });

      test('allows empty strings (isValid returns false)', () {
        const key = ServerRoomKey(serverId: '', roomId: '');

        expect(key.serverId, equals(''));
        expect(key.roomId, equals(''));
        expect(key.isValid, isFalse);
      });
    });

    group('equality', () {
      test('equal keys have same serverId and roomId', () {
        const key1 = ServerRoomKey(serverId: 'server1', roomId: 'room1');
        const key2 = ServerRoomKey(serverId: 'server1', roomId: 'room1');

        expect(key1, equals(key2));
        expect(key1 == key2, isTrue);
      });

      test('different serverIds are not equal', () {
        const key1 = ServerRoomKey(serverId: 'server1', roomId: 'room1');
        const key2 = ServerRoomKey(serverId: 'server2', roomId: 'room1');

        expect(key1, isNot(equals(key2)));
        expect(key1 == key2, isFalse);
      });

      test('different roomIds are not equal', () {
        const key1 = ServerRoomKey(serverId: 'server1', roomId: 'room1');
        const key2 = ServerRoomKey(serverId: 'server1', roomId: 'room2');

        expect(key1, isNot(equals(key2)));
        expect(key1 == key2, isFalse);
      });

      test('identical keys are equal', () {
        const key = ServerRoomKey(serverId: 'server1', roomId: 'room1');

        expect(key == key, isTrue);
      });
    });

    group('hashCode', () {
      test('equal keys have same hashCode', () {
        const key1 = ServerRoomKey(serverId: 'server1', roomId: 'room1');
        const key2 = ServerRoomKey(serverId: 'server1', roomId: 'room1');

        expect(key1.hashCode, equals(key2.hashCode));
      });

      test('hashCode is consistent', () {
        const key = ServerRoomKey(serverId: 'server1', roomId: 'room1');
        final hash1 = key.hashCode;
        final hash2 = key.hashCode;

        expect(hash1, equals(hash2));
      });

      test('can be used as Map key', () {
        const key1 = ServerRoomKey(serverId: 'server1', roomId: 'room1');
        const key2 = ServerRoomKey(serverId: 'server1', roomId: 'room1');

        final map = <ServerRoomKey, String>{key1: 'value1'};

        expect(map[key2], equals('value1'));
      });

      test('can be used in Set', () {
        const key1 = ServerRoomKey(serverId: 'server1', roomId: 'room1');
        const key2 = ServerRoomKey(serverId: 'server1', roomId: 'room1');
        const key3 = ServerRoomKey(serverId: 'server2', roomId: 'room1');

        // Build set incrementally to avoid equal_elements_in_set lint
        final set = <ServerRoomKey>{};
        set.add(key1);
        set.add(key2); // Should not increase size (equals key1)
        set.add(key3);

        expect(set.length, equals(2));
        expect(set.contains(key1), isTrue);
        expect(set.contains(key3), isTrue);
      });
    });

    group('toString', () {
      test('returns serverId:roomId format', () {
        const key = ServerRoomKey(serverId: 'server1', roomId: 'room1');

        expect(key.toString(), equals('server1:room1'));
      });

      test('handles special characters in IDs', () {
        const key = ServerRoomKey(serverId: 'server-1', roomId: 'room_1');

        expect(key.toString(), equals('server-1:room_1'));
      });
    });

    group('parse', () {
      test('parses valid key string', () {
        final key = ServerRoomKey.parse('server1:room1');

        expect(key.serverId, equals('server1'));
        expect(key.roomId, equals('room1'));
      });

      test('handles colons in roomId', () {
        final key = ServerRoomKey.parse('server1:room:with:colons');

        expect(key.serverId, equals('server1'));
        expect(key.roomId, equals('room:with:colons'));
      });

      test('throws FormatException for missing colon', () {
        expect(
          () => ServerRoomKey.parse('invalidkey'),
          throwsA(isA<FormatException>()),
        );
      });

      test('throws FormatException for empty serverId', () {
        expect(
          () => ServerRoomKey.parse(':room1'),
          throwsA(isA<FormatException>()),
        );
      });

      test('throws FormatException for empty roomId', () {
        expect(
          () => ServerRoomKey.parse('server1:'),
          throwsA(isA<FormatException>()),
        );
      });

      test('round-trips with toString', () {
        const original = ServerRoomKey(serverId: 'server1', roomId: 'room1');
        final parsed = ServerRoomKey.parse(original.toString());

        expect(parsed, equals(original));
      });
    });

    group('isValid', () {
      test('returns true for non-empty serverId and roomId', () {
        const key = ServerRoomKey(serverId: 'server1', roomId: 'room1');

        expect(key.isValid, isTrue);
      });

      test('returns false for empty serverId', () {
        const key = ServerRoomKey(serverId: '', roomId: 'room1');

        expect(key.isValid, isFalse);
      });

      test('returns false for empty roomId', () {
        const key = ServerRoomKey(serverId: 'server1', roomId: '');

        expect(key.isValid, isFalse);
      });

      test('returns false for both empty', () {
        const key = ServerRoomKey(serverId: '', roomId: '');

        expect(key.isValid, isFalse);
      });
    });

    group('copyWith', () {
      test('copies with new serverId', () {
        const original = ServerRoomKey(serverId: 'server1', roomId: 'room1');
        final copied = original.copyWith(serverId: 'server2');

        expect(copied.serverId, equals('server2'));
        expect(copied.roomId, equals('room1'));
      });

      test('copies with new roomId', () {
        const original = ServerRoomKey(serverId: 'server1', roomId: 'room1');
        final copied = original.copyWith(roomId: 'room2');

        expect(copied.serverId, equals('server1'));
        expect(copied.roomId, equals('room2'));
      });

      test('copies with both new values', () {
        const original = ServerRoomKey(serverId: 'server1', roomId: 'room1');
        final copied = original.copyWith(serverId: 'server2', roomId: 'room2');

        expect(copied.serverId, equals('server2'));
        expect(copied.roomId, equals('room2'));
      });

      test('copies with no changes', () {
        const original = ServerRoomKey(serverId: 'server1', roomId: 'room1');
        final copied = original.copyWith();

        expect(copied, equals(original));
      });
    });
  });
}
