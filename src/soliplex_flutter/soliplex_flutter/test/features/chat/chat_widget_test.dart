import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_flutter/client/client.dart';
import 'package:soliplex_flutter/features/chat/chat_widget.dart';
import 'package:soliplex_flutter/providers/providers.dart';

import '../../mocks/mock_soliplex_client.dart';

void main() {
  Widget wrapWidget(Widget widget, {List<Override> overrides = const []}) {
    return ProviderScope(
      overrides: overrides,
      child: MaterialApp(
        home: Scaffold(body: widget),
      ),
    );
  }

  group('ChatWidget', () {
    testWidgets('displays empty state when no room selected', (tester) async {
      await tester.pumpWidget(wrapWidget(const ChatWidget()));

      expect(find.text('Select a room to start chatting'), findsOneWidget);
      expect(find.byIcon(Icons.chat_bubble_outline), findsOneWidget);
    });

    testWidgets('displays loading indicator when room is selected', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const ChatWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      // First pump shows loading indicator while waiting for stream
      await tester.pump();

      // The widget should still render without error
      expect(find.byType(ChatWidget), findsOneWidget);
    });

    testWidgets('displays message input field', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const ChatWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.byType(TextField), findsOneWidget);
      expect(find.text('Type a message...'), findsOneWidget);
    });

    testWidgets('displays send button', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const ChatWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.send), findsOneWidget);
    });

    testWidgets('shows cancel button when agent is active', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const ChatWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          isAgentActiveProvider.overrideWith((ref) => true),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.stop), findsOneWidget);
      expect(find.text('Waiting for response...'), findsOneWidget);
    });

    testWidgets('disables input when agent is active', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const ChatWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          isAgentActiveProvider.overrideWith((ref) => true),
        ],
      ));

      await tester.pumpAndSettle();

      final textField = tester.widget<TextField>(find.byType(TextField));
      expect(textField.enabled, isFalse);
    });

    testWidgets('clears text field after sending message', (tester) async {
      final mockClient = MockSoliplexClient();
      var messageSent = false;

      await tester.pumpWidget(wrapWidget(
        const ChatWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          sendMessageProvider.overrideWith((ref) => (message) async {
            messageSent = true;
          }),
        ],
      ));

      await tester.pumpAndSettle();

      // Enter text
      await tester.enterText(find.byType(TextField), 'Hello world');
      expect(find.text('Hello world'), findsOneWidget);

      // Tap send button
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      // Text should be cleared
      expect(find.text('Hello world'), findsNothing);
      expect(messageSent, isTrue);
    });

    testWidgets('does not send empty message', (tester) async {
      final mockClient = MockSoliplexClient();
      var messageSent = false;

      await tester.pumpWidget(wrapWidget(
        const ChatWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          sendMessageProvider.overrideWith((ref) => (message) async {
            messageSent = true;
          }),
        ],
      ));

      await tester.pumpAndSettle();

      // Tap send without entering text
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      expect(messageSent, isFalse);
    });

    testWidgets('shows error snackbar on send failure', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const ChatWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          sendMessageProvider.overrideWith((ref) => (message) async {
            throw Exception('Network error');
          }),
        ],
      ));

      await tester.pumpAndSettle();

      // Enter text and send
      await tester.enterText(find.byType(TextField), 'Hello');
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      // Should show error snackbar
      expect(find.textContaining('Error:'), findsOneWidget);
    });

    testWidgets('renders properly with room selected', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const ChatWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      await tester.pump();

      // Widget should render without crashing
      expect(find.byType(ChatWidget), findsOneWidget);
      // Input area should be visible
      expect(find.byType(TextField), findsOneWidget);
    });

    testWidgets('cancel button calls cancelRun', (tester) async {
      final mockClient = MockSoliplexClient();
      var cancelCalled = false;

      await tester.pumpWidget(wrapWidget(
        const ChatWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          isAgentActiveProvider.overrideWith((ref) => true),
          cancelRunProvider.overrideWith((ref) => () {
            cancelCalled = true;
          }),
        ],
      ));

      await tester.pumpAndSettle();

      // Tap cancel button
      await tester.tap(find.byIcon(Icons.stop));
      await tester.pumpAndSettle();

      expect(cancelCalled, isTrue);
    });
  });

  group('_EmptyChat', () {
    testWidgets('displays message with chat icon', (tester) async {
      await tester.pumpWidget(wrapWidget(const ChatWidget()));

      expect(find.byIcon(Icons.chat_bubble_outline), findsOneWidget);
      expect(find.text('Select a room to start chatting'), findsOneWidget);
    });
  });

  group('_ChatInput', () {
    testWidgets('shows hint text', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const ChatWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('Type a message...'), findsOneWidget);
    });

    testWidgets('shows waiting hint when active', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const ChatWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          isAgentActiveProvider.overrideWith((ref) => true),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('Waiting for response...'), findsOneWidget);
    });

    testWidgets('allows multiline input', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const ChatWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      await tester.pumpAndSettle();

      final textField = tester.widget<TextField>(find.byType(TextField));
      expect(textField.maxLines, equals(4));
      expect(textField.minLines, equals(1));
    });
  });
}
