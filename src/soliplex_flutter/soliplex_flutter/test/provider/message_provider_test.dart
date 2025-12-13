import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_flutter/client/client.dart';
import 'package:soliplex_flutter/providers/client_provider.dart';
import 'package:soliplex_flutter/providers/message_provider.dart';
import 'package:soliplex_flutter/providers/room_provider.dart';

import '../mocks/mock_soliplex_client.dart';

void main() {
  group('messagesProvider', () {
    test('returns empty stream when no room selected', () async {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      // Ensure no room is selected
      expect(container.read(currentRoomProvider), isNull);

      // messagesProvider should return empty stream when no room
      final messagesAsync = container.read(messagesProvider);

      expect(messagesAsync, isA<AsyncValue<dynamic>>());
      expect(messagesAsync.hasValue, isFalse);
    });

    test('streams messages for current room', () async {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      // Set current room
      container.read(currentRoomProvider.notifier).state = 'room1';

      // Wait for messages
      final messagesAsync = await container.read(messagesProvider.future);

      expect(messagesAsync, isA<List<ChatMessage>>());
      expect(messagesAsync, isNotEmpty);
      expect(mockClient.getMessageStreamCalled, isTrue);
    });
  });

  group('roomMessagesProvider', () {
    test('streams messages for specific room', () async {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      // Stream messages for specific room
      final messagesAsync = await container.read(roomMessagesProvider('room1').future);

      expect(messagesAsync, isA<List<ChatMessage>>());
      expect(messagesAsync, isNotEmpty);
      expect(mockClient.getMessageStreamCalled, isTrue);
    });
  });

  group('currentMessagesProvider', () {
    test('returns empty list when no room selected', () {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      // Ensure no room is selected
      expect(container.read(currentRoomProvider), isNull);

      // currentMessagesProvider should return empty list
      final messages = container.read(currentMessagesProvider);

      expect(messages, isEmpty);
    });

    test('returns messages for current room', () {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      // Set current room
      container.read(currentRoomProvider.notifier).state = 'room1';

      // Get current messages
      final messages = container.read(currentMessagesProvider);

      expect(messages, isA<List<ChatMessage>>());
      expect(messages, isNotEmpty);
      expect(mockClient.getMessagesCalled, isTrue);
    });
  });
}
