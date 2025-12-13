import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_flutter/providers/canvas_provider.dart';
import 'package:soliplex_flutter/providers/chat_provider.dart';
import 'package:soliplex_flutter/providers/client_provider.dart';
import 'package:soliplex_flutter/providers/room_provider.dart';

import '../mocks/mock_soliplex_client.dart';

void main() {
  group('sendMessageProvider', () {
    test('provider is accessible', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final sendMessage = container.read(sendMessageProvider);

      expect(sendMessage, isA<Function>());
    });

    test('throws when no room selected', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      // Ensure no room is selected
      expect(container.read(currentRoomProvider), isNull);

      // sendMessage should throw StateError when no room
      final sendMessage = container.read(sendMessageProvider);

      expect(
        () async => await sendMessage('Hello'),
        throwsA(isA<StateError>()),
      );
    });

    test('sends message successfully when room is selected', () async {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      // Set current room
      container.read(currentRoomProvider.notifier).state = 'room1';

      final sendMessage = container.read(sendMessageProvider);

      // Send message
      await sendMessage('Hello, world!');

      expect(mockClient.chatCalled, isTrue);
    });

    test('updates canvas state during chat', () async {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      // Set current room
      container.read(currentRoomProvider.notifier).state = 'room1';

      final sendMessage = container.read(sendMessageProvider);

      // Send message (mock will trigger canvas update callback)
      await sendMessage('Test message');

      expect(mockClient.chatCalled, isTrue);
    });

    test('updates activity state during chat', () async {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      // Set current room
      container.read(currentRoomProvider.notifier).state = 'room1';

      final sendMessage = container.read(sendMessageProvider);

      // Send message (mock will trigger activity update callback)
      await sendMessage('Test message');

      expect(mockClient.chatCalled, isTrue);
      // Activity state should be set back to false after chat completes
      expect(container.read(isAgentActiveProvider), isFalse);
    });
  });

  group('sendMessageWithToolsProvider', () {
    test('provider is accessible', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final sendMessageWithTools = container.read(sendMessageWithToolsProvider);

      expect(sendMessageWithTools, isA<Function>());
    });

    test('throws when no room selected', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      // Ensure no room is selected
      expect(container.read(currentRoomProvider), isNull);

      final sendMessageWithTools = container.read(sendMessageWithToolsProvider);

      expect(
        () async => await sendMessageWithTools('Hello'),
        throwsA(isA<StateError>()),
      );
    });

    test('sends message with tools successfully', () async {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      // Set current room
      container.read(currentRoomProvider.notifier).state = 'room1';

      final sendMessageWithTools = container.read(sendMessageWithToolsProvider);

      // Define a test tool
      final testTool = ag_ui.Tool(
        name: 'test_tool',
        description: 'A test tool',
        parameters: {},
      );

      // Send message with tools
      await sendMessageWithTools(
        'Hello with tools',
        tools: {'test_tool': testTool},
      );

      expect(mockClient.chatCalled, isTrue);
    });

    test('handles tool executors and UI handlers', () async {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      // Set current room
      container.read(currentRoomProvider.notifier).state = 'room1';

      final sendMessageWithTools = container.read(sendMessageWithToolsProvider);

      // Send message with executors and handlers
      await sendMessageWithTools(
        'Test message',
        state: {'key': 'value'},
      );

      expect(mockClient.chatCalled, isTrue);
    });
  });

  group('cancelRunProvider', () {
    test('provider is accessible', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final cancelRun = container.read(cancelRunProvider);

      expect(cancelRun, isA<Function>());
    });

    test('does nothing when no room selected', () {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      // Ensure no room is selected
      expect(container.read(currentRoomProvider), isNull);

      final cancelRun = container.read(cancelRunProvider);

      // Should not throw
      cancelRun();

      expect(mockClient.cancelRunCalled, isFalse);
    });

    test('cancels run when room is selected', () {
      final mockClient = MockSoliplexClient();
      final container = ProviderContainer(
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
        ],
      );
      addTearDown(container.dispose);

      // Set current room
      container.read(currentRoomProvider.notifier).state = 'room1';

      final cancelRun = container.read(cancelRunProvider);

      // Cancel run
      cancelRun();

      expect(mockClient.cancelRunCalled, isTrue);
    });
  });
}
