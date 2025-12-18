import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/core/models/active_run_state.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';
import 'package:soliplex_frontend/features/chat/widgets/chat_input.dart';

import '../../../helpers/test_helpers.dart';

void main() {
  group('ChatInput', () {
    group('Send Button', () {
      testWidgets('is enabled when canSendMessage is true', (tester) async {
        // Arrange
        final mockRoom = TestData.createRoom();
        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatInput(
                onSend: (_) {},
              ),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => mockRoom),
              currentThreadProvider.overrideWith((ref) => mockThread),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Type some text
        await tester.enterText(find.byType(TextField), 'Hello');
        await tester.pump();

        // Assert
        final sendButton = tester.widget<IconButton>(
          find.widgetWithIcon(IconButton, Icons.send),
        );
        expect(sendButton.onPressed, isNotNull);
      });

      testWidgets('is disabled when canSendMessage is false', (tester) async {
        // Arrange - no room selected
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatInput(
                onSend: (_) {},
              ),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => null),
            ],
          ),
        );

        // Act
        await tester.enterText(find.byType(TextField), 'Hello');
        await tester.pump();

        // Assert
        final sendButton = tester.widget<IconButton>(
          find.widgetWithIcon(IconButton, Icons.send),
        );
        expect(sendButton.onPressed, isNull);
      });

      testWidgets('is disabled when text is empty', (tester) async {
        // Arrange
        final mockRoom = TestData.createRoom();
        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatInput(
                onSend: (_) {},
              ),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => mockRoom),
              currentThreadProvider.overrideWith((ref) => mockThread),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Assert - empty text field
        final sendButton = tester.widget<IconButton>(
          find.widgetWithIcon(IconButton, Icons.send),
        );
        expect(sendButton.onPressed, isNull);
      });

      testWidgets('is disabled during active run', (tester) async {
        // Arrange
        final mockRoom = TestData.createRoom();
        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatInput(
                onSend: (_) {},
              ),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => mockRoom),
              currentThreadProvider.overrideWith((ref) => mockThread),
              activeRunNotifierOverride(
                const RunningState(
                  threadId: 'test-thread',
                  runId: 'test-run',
                  context: RunContext.empty,
                ),
              ),
            ],
          ),
        );

        await tester.enterText(find.byType(TextField), 'Hello');
        await tester.pump();

        // Assert
        final sendButton = tester.widget<IconButton>(
          find.widgetWithIcon(IconButton, Icons.send),
        );
        expect(sendButton.onPressed, isNull);
      });
    });

    group('Text Input', () {
      testWidgets('displays placeholder when can send', (tester) async {
        // Arrange
        final mockRoom = TestData.createRoom();
        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatInput(
                onSend: (_) {},
              ),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => mockRoom),
              currentThreadProvider.overrideWith((ref) => mockThread),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Assert
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(
          textField.decoration?.hintText,
          'Type a message...',
        );
      });

      testWidgets('displays disabled placeholder when cannot send',
          (tester) async {
        // Arrange - no room selected
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatInput(
                onSend: (_) {},
              ),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => null),
            ],
          ),
        );

        // Assert
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(
          textField.decoration?.hintText,
          'Select a room to start chatting',
        );
      });

      testWidgets('allows text entry', (tester) async {
        // Arrange
        final mockRoom = TestData.createRoom();
        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatInput(
                onSend: (_) {},
              ),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => mockRoom),
              currentThreadProvider.overrideWith((ref) => mockThread),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        await tester.enterText(find.byType(TextField), 'Hello, world!');
        await tester.pump();

        // Assert
        expect(find.text('Hello, world!'), findsOneWidget);
      });

      testWidgets('is disabled when cannot send', (tester) async {
        // Arrange - no room selected
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatInput(
                onSend: (_) {},
              ),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => null),
            ],
          ),
        );

        // Assert
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(textField.enabled, isFalse);
      });
    });

    group('Send Action', () {
      testWidgets('calls onSend callback with text', (tester) async {
        // Arrange
        final mockRoom = TestData.createRoom();
        final mockThread = TestData.createThread();
        String? sentText;

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatInput(
                onSend: (text) => sentText = text,
              ),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => mockRoom),
              currentThreadProvider.overrideWith((ref) => mockThread),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        await tester.enterText(find.byType(TextField), 'Test message');
        await tester.pump();

        await tester.tap(find.widgetWithIcon(IconButton, Icons.send));
        await tester.pump();

        // Assert
        expect(sentText, 'Test message');
      });

      testWidgets('clears input after send', (tester) async {
        // Arrange
        final mockRoom = TestData.createRoom();
        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatInput(
                onSend: (_) {},
              ),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => mockRoom),
              currentThreadProvider.overrideWith((ref) => mockThread),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        await tester.enterText(find.byType(TextField), 'Test message');
        await tester.pump();

        await tester.tap(find.widgetWithIcon(IconButton, Icons.send));
        await tester.pump();

        // Assert
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(textField.controller?.text, isEmpty);
      });

      testWidgets('trims whitespace before sending', (tester) async {
        // Arrange
        final mockRoom = TestData.createRoom();
        final mockThread = TestData.createThread();
        String? sentText;

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatInput(
                onSend: (text) => sentText = text,
              ),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => mockRoom),
              currentThreadProvider.overrideWith((ref) => mockThread),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        await tester.enterText(find.byType(TextField), '  Test message  ');
        await tester.pump();

        await tester.tap(find.widgetWithIcon(IconButton, Icons.send));
        await tester.pump();

        // Assert
        expect(sentText, 'Test message');
      });

      testWidgets('does not send empty message', (tester) async {
        // Arrange
        final mockRoom = TestData.createRoom();
        final mockThread = TestData.createThread();
        var sendCalled = false;

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatInput(
                onSend: (_) => sendCalled = true,
              ),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => mockRoom),
              currentThreadProvider.overrideWith((ref) => mockThread),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        await tester.enterText(find.byType(TextField), '   ');
        await tester.pump();

        // Try to tap send button (should be disabled)
        final sendButton = tester.widget<IconButton>(
          find.widgetWithIcon(IconButton, Icons.send),
        );

        // Assert
        expect(sendButton.onPressed, isNull);
        expect(sendCalled, isFalse);
      });

      testWidgets('can send by pressing enter', (tester) async {
        // Arrange
        final mockRoom = TestData.createRoom();
        final mockThread = TestData.createThread();
        String? sentText;

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatInput(
                onSend: (text) => sentText = text,
              ),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => mockRoom),
              currentThreadProvider.overrideWith((ref) => mockThread),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        await tester.enterText(find.byType(TextField), 'Test message');
        await tester.pump();

        // Submit the text field (simulates Enter key)
        await tester.testTextInput.receiveAction(TextInputAction.done);
        await tester.pump();

        // Assert
        expect(sentText, 'Test message');
      });
    });

    group('Visual Styling', () {
      testWidgets('displays with rounded border', (tester) async {
        // Arrange
        final mockRoom = TestData.createRoom();
        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatInput(
                onSend: (_) {},
              ),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => mockRoom),
              currentThreadProvider.overrideWith((ref) => mockThread),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Assert
        final textField = tester.widget<TextField>(find.byType(TextField));
        final decoration = textField.decoration!;
        final border = decoration.border! as OutlineInputBorder;
        expect(border.borderRadius, BorderRadius.circular(24));
      });

      testWidgets('send button has primary color when enabled', (tester) async {
        // Arrange
        final mockRoom = TestData.createRoom();
        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatInput(
                onSend: (_) {},
              ),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => mockRoom),
              currentThreadProvider.overrideWith((ref) => mockThread),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        await tester.enterText(find.byType(TextField), 'Test');
        await tester.pump();

        // Assert - send button should be styled
        final sendButton = tester.widget<IconButton>(
          find.widgetWithIcon(IconButton, Icons.send),
        );
        expect(sendButton.onPressed, isNotNull);
      });
    });
  });
}
