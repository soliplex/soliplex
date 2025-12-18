import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';

import '../../helpers/test_helpers.dart';

void main() {
  group('roomsProvider', () {
    late MockSoliplexApi mockApi;

    setUp(() {
      mockApi = MockSoliplexApi();
    });

    test('returns list of rooms from API', () async {
      // Arrange
      final mockRooms = [
        TestData.createRoom(id: 'general', name: 'General'),
        TestData.createRoom(id: 'technical', name: 'Technical'),
        TestData.createRoom(id: 'research', name: 'Research'),
      ];
      when(() => mockApi.getRooms()).thenAnswer((_) async => mockRooms);

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
        ],
      );
      addTearDown(container.dispose);

      // Act
      final rooms = await container.read(roomsProvider.future);

      // Assert
      expect(rooms, hasLength(3));
      expect(rooms[0].id, 'general');
      expect(rooms[1].id, 'technical');
      expect(rooms[2].id, 'research');
      verify(() => mockApi.getRooms()).called(1);
    });

    test('propagates NetworkException from API', () async {
      // Arrange
      when(() => mockApi.getRooms()).thenThrow(
        const NetworkException(message: 'Connection failed', isTimeout: true),
      );

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
        ],
      );
      addTearDown(container.dispose);

      // Act - Wait for state with error using a completer
      final completer = Completer<AsyncValue<List<Room>>>();
      container
        ..listen(roomsProvider, (_, next) {
          if (next.hasError) {
            completer.complete(next);
          }
        })
        ..read(roomsProvider); // Trigger the provider
      final state = await completer.future.timeout(
        const Duration(seconds: 5),
        onTimeout: () => container.read(roomsProvider),
      );

      // Assert - In Riverpod 3.0, state.hasError indicates error presence
      expect(state.hasError, isTrue);
      expect(state.error, isA<NetworkException>());
    });

    test('propagates AuthException from API', () async {
      // Arrange
      when(() => mockApi.getRooms()).thenThrow(
        const AuthException(message: 'Unauthorized', statusCode: 401),
      );

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
        ],
      );
      addTearDown(container.dispose);

      // Act - Wait for state with error using a completer
      final completer = Completer<AsyncValue<List<Room>>>();
      container
        ..listen(roomsProvider, (_, next) {
          if (next.hasError) {
            completer.complete(next);
          }
        })
        ..read(roomsProvider);
      final state = await completer.future.timeout(
        const Duration(seconds: 5),
        onTimeout: () => container.read(roomsProvider),
      );

      // Assert
      expect(state.hasError, isTrue);
      expect(state.error, isA<AuthException>());
    });

    test('propagates ApiException from API', () async {
      // Arrange
      when(() => mockApi.getRooms()).thenThrow(
        const ApiException(
          message: 'Internal server error',
          statusCode: 500,
        ),
      );

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
        ],
      );
      addTearDown(container.dispose);

      // Act - Wait for state with error using a completer
      final completer = Completer<AsyncValue<List<Room>>>();
      container
        ..listen(roomsProvider, (_, next) {
          if (next.hasError) {
            completer.complete(next);
          }
        })
        ..read(roomsProvider);
      final state = await completer.future.timeout(
        const Duration(seconds: 5),
        onTimeout: () => container.read(roomsProvider),
      );

      // Assert
      expect(state.hasError, isTrue);
      expect(state.error, isA<ApiException>());
    });

    test('can be refreshed to fetch fresh data', () async {
      // Arrange
      final mockRooms1 = [
        TestData.createRoom(id: 'general', name: 'General'),
      ];
      final mockRooms2 = [
        TestData.createRoom(id: 'general', name: 'General'),
        TestData.createRoom(id: 'tech', name: 'Tech'),
      ];

      when(() => mockApi.getRooms()).thenAnswer((_) async => mockRooms1);

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
        ],
      );
      addTearDown(container.dispose);

      // Act - First fetch
      final rooms1 = await container.read(roomsProvider.future);
      expect(rooms1, hasLength(1));

      // Update mock for second fetch
      when(() => mockApi.getRooms()).thenAnswer((_) async => mockRooms2);

      // Refresh and fetch again
      container.refresh(roomsProvider);
      final rooms2 = await container.read(roomsProvider.future);

      // Assert
      expect(rooms2, hasLength(2));
      verify(() => mockApi.getRooms()).called(2);
    });

    test('returns empty list when API returns no rooms', () async {
      // Arrange
      when(() => mockApi.getRooms()).thenAnswer((_) async => []);

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
        ],
      );
      addTearDown(container.dispose);

      // Act
      final rooms = await container.read(roomsProvider.future);

      // Assert
      expect(rooms, isEmpty);
      verify(() => mockApi.getRooms()).called(1);
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

  group('currentRoomProvider', () {
    late MockSoliplexApi mockApi;

    setUp(() {
      mockApi = MockSoliplexApi();
    });

    test('returns null when no room is selected', () {
      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
        ],
      );
      addTearDown(container.dispose);

      final room = container.read(currentRoomProvider);

      expect(room, isNull);
    });

    test('returns selected room when room ID is set', () async {
      // Arrange
      final mockRooms = [
        TestData.createRoom(id: 'general', name: 'General'),
        TestData.createRoom(id: 'tech', name: 'Tech'),
      ];
      when(() => mockApi.getRooms()).thenAnswer((_) async => mockRooms);

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
        ],
      );
      addTearDown(container.dispose);

      // Wait for rooms to load
      await container.read(roomsProvider.future);

      // Act - Select a room
      container.read(currentRoomIdProvider.notifier).state = 'tech';

      // Assert
      final room = container.read(currentRoomProvider);
      expect(room, isNotNull);
      expect(room!.id, 'tech');
      expect(room.name, 'Tech');
    });

    test('returns null when selected room is not found', () async {
      // Arrange
      final mockRooms = [
        TestData.createRoom(id: 'general', name: 'General'),
      ];
      when(() => mockApi.getRooms()).thenAnswer((_) async => mockRooms);

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
        ],
      );
      addTearDown(container.dispose);

      // Wait for rooms to load
      await container.read(roomsProvider.future);

      // Act - Select a non-existent room
      container.read(currentRoomIdProvider.notifier).state = 'nonexistent';

      // Assert
      final room = container.read(currentRoomProvider);
      expect(room, isNull);
    });

    test('returns null when rooms are still loading', () {
      // Arrange
      when(() => mockApi.getRooms()).thenAnswer(
        (_) => Future.delayed(
          const Duration(seconds: 1),
          () => [TestData.createRoom()],
        ),
      );

      final container = ProviderContainer(
        overrides: [
          apiProvider.overrideWithValue(mockApi),
        ],
      );
      addTearDown(container.dispose);

      // Act - Select a room while still loading
      container.read(currentRoomIdProvider.notifier).state = 'test-room';

      // Assert
      final room = container.read(currentRoomProvider);
      expect(room, isNull);
    });
  });
}
