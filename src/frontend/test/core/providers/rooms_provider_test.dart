import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';

void main() {
  group('roomsProvider', () {
    test('returns list of mock rooms', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final rooms = await container.read(roomsProvider.future);

      expect(rooms, hasLength(3));
      expect(rooms[0].id, 'general');
      expect(rooms[1].id, 'technical');
      expect(rooms[2].id, 'research');
    });
  });

  group('currentRoomIdProvider', () {
    test('starts with null', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final roomId = container.read(currentRoomIdProvider);

      expect(roomId, isNull);
    });

    test('can be updated', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      container.read(currentRoomIdProvider.notifier).state = 'general';

      expect(container.read(currentRoomIdProvider), 'general');
    });
  });
}
