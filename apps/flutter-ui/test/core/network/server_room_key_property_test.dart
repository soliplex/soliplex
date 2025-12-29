import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/core/network/server_room_key.dart';

/// Property-based tests for ServerRoomKey.
///
/// These tests verify invariants that must hold for ALL possible inputs,
/// not just specific example cases. This catches edge cases that might
/// be missed by traditional example-based tests.
void main() {
  group('ServerRoomKey Property-Based Tests', () {
    late Random random;

    setUp(() {
      // Use fixed seed for reproducibility in CI
      random = Random(42);
    });

    /// Generates a random string of given length.
    String randomString(int length) {
      const chars =
          'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_';
      return List.generate(
        length,
        (_) => chars[random.nextInt(chars.length)],
      ).join();
    }

    /// Generates a random string that may contain colons.
    String randomStringWithColons(int length) {
      const chars =
          'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_:';
      return List.generate(
        length,
        (_) => chars[random.nextInt(chars.length)],
      ).join();
    }

    group('Equality Invariants', () {
      test('reflexivity: x == x for all x', () {
        for (var i = 0; i < 100; i++) {
          final key = ServerRoomKey(
            serverId: randomString(random.nextInt(20) + 1),
            roomId: randomString(random.nextInt(20) + 1),
          );

          expect(key == key, isTrue, reason: 'Key should equal itself: $key');
        }
      });

      test('symmetry: x == y implies y == x', () {
        for (var i = 0; i < 100; i++) {
          final serverId = randomString(random.nextInt(20) + 1);
          final roomId = randomString(random.nextInt(20) + 1);

          final key1 = ServerRoomKey(serverId: serverId, roomId: roomId);
          final key2 = ServerRoomKey(serverId: serverId, roomId: roomId);

          expect(key1 == key2, isTrue);
          expect(key2 == key1, isTrue);
        }
      });

      test('transitivity: x == y and y == z implies x == z', () {
        for (var i = 0; i < 100; i++) {
          final serverId = randomString(random.nextInt(20) + 1);
          final roomId = randomString(random.nextInt(20) + 1);

          final key1 = ServerRoomKey(serverId: serverId, roomId: roomId);
          final key2 = ServerRoomKey(serverId: serverId, roomId: roomId);
          final key3 = ServerRoomKey(serverId: serverId, roomId: roomId);

          expect(key1 == key2, isTrue);
          expect(key2 == key3, isTrue);
          expect(key1 == key3, isTrue);
        }
      });

      test('inequality: different values are never equal', () {
        for (var i = 0; i < 100; i++) {
          final key1 = ServerRoomKey(
            serverId: randomString(random.nextInt(20) + 1),
            roomId: randomString(random.nextInt(20) + 1),
          );

          // Different serverId
          final key2 = ServerRoomKey(
            serverId: '${key1.serverId}_different',
            roomId: key1.roomId,
          );

          // Different roomId
          final key3 = ServerRoomKey(
            serverId: key1.serverId,
            roomId: '${key1.roomId}_different',
          );

          expect(key1 == key2, isFalse);
          expect(key1 == key3, isFalse);
        }
      });
    });

    group('HashCode Invariants', () {
      test('consistency: hashCode returns same value on repeated calls', () {
        for (var i = 0; i < 100; i++) {
          final key = ServerRoomKey(
            serverId: randomString(random.nextInt(20) + 1),
            roomId: randomString(random.nextInt(20) + 1),
          );

          final hash1 = key.hashCode;
          final hash2 = key.hashCode;
          final hash3 = key.hashCode;

          expect(hash1, equals(hash2));
          expect(hash2, equals(hash3));
        }
      });

      test('equal objects have equal hashCodes', () {
        for (var i = 0; i < 100; i++) {
          final serverId = randomString(random.nextInt(20) + 1);
          final roomId = randomString(random.nextInt(20) + 1);

          final key1 = ServerRoomKey(serverId: serverId, roomId: roomId);
          final key2 = ServerRoomKey(serverId: serverId, roomId: roomId);

          expect(key1 == key2, isTrue);
          expect(
            key1.hashCode,
            equals(key2.hashCode),
            reason: 'Equal keys must have equal hashCodes',
          );
        }
      });

      test('hashCode distribution is reasonable (low collision rate)', () {
        final hashes = <int>{};
        const numKeys = 1000;

        for (var i = 0; i < numKeys; i++) {
          final key = ServerRoomKey(
            serverId: randomString(random.nextInt(20) + 1),
            roomId: randomString(random.nextInt(20) + 1),
          );
          hashes.add(key.hashCode);
        }

        // With 1000 random keys, we expect very few collisions
        // Allow up to 5% collision rate
        final collisionRate = 1 - (hashes.length / numKeys);
        expect(
          collisionRate,
          lessThan(0.05),
          reason:
              'Hash collision rate should be < 5%, got ${collisionRate * 100}%',
        );
      });
    });

    group('Parse/ToString Round-Trip', () {
      test('toString followed by parse returns equal key', () {
        for (var i = 0; i < 100; i++) {
          // Use serverId without colons to ensure valid parse
          final serverId = randomString(random.nextInt(20) + 1);
          // roomId can have colons
          final roomId = randomStringWithColons(random.nextInt(20) + 1);

          final original = ServerRoomKey(serverId: serverId, roomId: roomId);
          final serialized = original.toString();
          final parsed = ServerRoomKey.parse(serialized);

          expect(parsed, equals(original));
          expect(parsed.serverId, equals(original.serverId));
          expect(parsed.roomId, equals(original.roomId));
        }
      });

      test('parse preserves colons in roomId', () {
        for (var i = 0; i < 50; i++) {
          final serverId = randomString(random.nextInt(10) + 1);
          // Generate roomId with guaranteed colons
          final roomIdParts = List.generate(
            random.nextInt(3) + 2,
            (_) => randomString(random.nextInt(5) + 1),
          );
          final roomId = roomIdParts.join(':');

          final original = ServerRoomKey(serverId: serverId, roomId: roomId);
          final parsed = ServerRoomKey.parse(original.toString());

          expect(parsed.roomId, equals(roomId));
        }
      });
    });

    group('CopyWith Invariants', () {
      test('copyWith() with no args returns equal key', () {
        for (var i = 0; i < 100; i++) {
          final original = ServerRoomKey(
            serverId: randomString(random.nextInt(20) + 1),
            roomId: randomString(random.nextInt(20) + 1),
          );

          final copied = original.copyWith();

          expect(copied, equals(original));
        }
      });

      test('copyWith preserves unchanged fields', () {
        for (var i = 0; i < 100; i++) {
          final original = ServerRoomKey(
            serverId: randomString(random.nextInt(20) + 1),
            roomId: randomString(random.nextInt(20) + 1),
          );

          final newServerId = randomString(random.nextInt(20) + 1);
          final newRoomId = randomString(random.nextInt(20) + 1);

          // Change only serverId
          final copy1 = original.copyWith(serverId: newServerId);
          expect(copy1.serverId, equals(newServerId));
          expect(copy1.roomId, equals(original.roomId));

          // Change only roomId
          final copy2 = original.copyWith(roomId: newRoomId);
          expect(copy2.serverId, equals(original.serverId));
          expect(copy2.roomId, equals(newRoomId));
        }
      });

      test('copyWith does not mutate original', () {
        for (var i = 0; i < 100; i++) {
          final original = ServerRoomKey(
            serverId: randomString(random.nextInt(20) + 1),
            roomId: randomString(random.nextInt(20) + 1),
          );

          final originalServerId = original.serverId;
          final originalRoomId = original.roomId;

          // Perform copyWith
          original.copyWith(
            serverId: randomString(10),
            roomId: randomString(10),
          );

          // Original unchanged
          expect(original.serverId, equals(originalServerId));
          expect(original.roomId, equals(originalRoomId));
        }
      });
    });

    group('IsValid Invariants', () {
      test('isValid is true iff both fields are non-empty', () {
        for (var i = 0; i < 100; i++) {
          final serverId = random.nextBool()
              ? randomString(random.nextInt(20) + 1)
              : '';
          final roomId = random.nextBool()
              ? randomString(random.nextInt(20) + 1)
              : '';

          final key = ServerRoomKey(serverId: serverId, roomId: roomId);
          final expectedValid = serverId.isNotEmpty && roomId.isNotEmpty;

          expect(
            key.isValid,
            equals(expectedValid),
            reason:
                // ignore: lines_longer_than_80_chars (auto-documented)
                'isValid should be $expectedValid for serverId="$serverId", roomId="$roomId"', // ignore: lines_longer_than_80_chars
          );
        }
      });
    });

    group('Map/Set Usage', () {
      test('can store and retrieve from Map with random keys', () {
        final map = <ServerRoomKey, int>{};

        // Insert random keys
        final insertedKeys = <ServerRoomKey>[];
        for (var i = 0; i < 100; i++) {
          final key = ServerRoomKey(
            serverId: randomString(random.nextInt(20) + 1),
            roomId: randomString(random.nextInt(20) + 1),
          );
          map[key] = i;
          insertedKeys.add(key);
        }

        // Verify retrieval with equivalent keys
        for (var i = 0; i < insertedKeys.length; i++) {
          final originalKey = insertedKeys[i];
          final lookupKey = ServerRoomKey(
            serverId: originalKey.serverId,
            roomId: originalKey.roomId,
          );

          expect(map[lookupKey], equals(i));
        }
      });

      test('Set correctly deduplicates equivalent keys', () {
        final set = <ServerRoomKey>{};
        const iterations = 100;

        // Add each key twice
        for (var i = 0; i < iterations; i++) {
          final serverId = randomString(random.nextInt(20) + 1);
          final roomId = randomString(random.nextInt(20) + 1);

          final key1 = ServerRoomKey(serverId: serverId, roomId: roomId);
          final key2 = ServerRoomKey(serverId: serverId, roomId: roomId);

          set.add(key1);
          set.add(key2);
        }

        // Each unique combination should appear only once
        expect(set.length, equals(iterations));
      });
    });

    group('Edge Cases', () {
      test('handles very long strings', () {
        final longServerId = randomString(1000);
        final longRoomId = randomString(1000);

        final key1 = ServerRoomKey(serverId: longServerId, roomId: longRoomId);
        final key2 = ServerRoomKey(serverId: longServerId, roomId: longRoomId);

        expect(key1, equals(key2));
        expect(key1.hashCode, equals(key2.hashCode));
        expect(ServerRoomKey.parse(key1.toString()), equals(key1));
      });

      test('handles single character strings', () {
        for (var i = 0; i < 26; i++) {
          final char = String.fromCharCode('a'.codeUnitAt(0) + i);
          final key = ServerRoomKey(serverId: char, roomId: char);

          expect(key.isValid, isTrue);
          expect(key.toString(), equals('$char:$char'));
          expect(ServerRoomKey.parse(key.toString()), equals(key));
        }
      });

      test('handles special characters in IDs', () {
        final specialChars = ['-', '_', '.', '~', '!', '@', '#', r'$', '%'];

        for (final char in specialChars) {
          final key = ServerRoomKey(
            serverId: 'server${char}id',
            roomId: 'room${char}id',
          );

          expect(key.isValid, isTrue);
          expect(ServerRoomKey.parse(key.toString()), equals(key));
        }
      });

      test('handles numeric-only IDs', () {
        for (var i = 0; i < 50; i++) {
          final numericServerId = random.nextInt(1000000).toString();
          final numericRoomId = random.nextInt(1000000).toString();

          final key = ServerRoomKey(
            serverId: numericServerId,
            roomId: numericRoomId,
          );

          expect(key.isValid, isTrue);
          expect(ServerRoomKey.parse(key.toString()), equals(key));
        }
      });
    });
  });
}
