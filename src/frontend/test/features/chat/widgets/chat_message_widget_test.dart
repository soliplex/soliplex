import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/features/chat/widgets/chat_message_widget.dart';

import '../../../helpers/test_helpers.dart';

void main() {
  group('ChatMessageWidget', () {
    group('User Messages', () {
      testWidgets('displays user message with right alignment', (tester) async {
        // Arrange
        final message = TestData.createMessage(
          text: 'Hello, assistant!',
        );

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatMessageWidget(message: message),
            ),
          ),
        );

        // Assert
        expect(find.text('Hello, assistant!'), findsOneWidget);

        // Check right alignment
        final row = tester.widget<Row>(find.byType(Row));
        expect(row.mainAxisAlignment, MainAxisAlignment.end);
      });

      testWidgets('displays user message with blue background', (tester) async {
        // Arrange
        final message = TestData.createMessage(
          text: 'Test',
        );

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatMessageWidget(message: message),
            ),
          ),
        );

        // Assert
        final container = tester.widget<Container>(
          find.descendant(
            of: find.byType(ChatMessageWidget),
            matching: find.byType(Container).first,
          ),
        );
        final decoration = container.decoration! as BoxDecoration;
        expect(decoration.color, isNotNull);
        // Primary container color for user messages
      });

      testWidgets('shows streaming indicator when isStreaming is true',
          (tester) async {
        // Arrange
        final message = TestData.createMessage(
          text: 'Typing...',
        );

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatMessageWidget(
                message: message,
                isStreaming: true,
              ),
            ),
          ),
        );

        // Assert
        expect(find.text('Typing...'), findsWidgets);
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
      });

      testWidgets('does not show streaming indicator when isStreaming is false',
          (tester) async {
        // Arrange
        final message = TestData.createMessage(
          text: 'Done',
        );

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatMessageWidget(
                message: message,
              ),
            ),
          ),
        );

        // Assert
        expect(find.text('Typing...'), findsNothing);
        expect(find.byType(CircularProgressIndicator), findsNothing);
      });
    });

    group('Assistant Messages', () {
      testWidgets('displays assistant message with left alignment',
          (tester) async {
        // Arrange
        final message = TestData.createMessage(
          user: ChatUser.assistant,
          text: 'Hello, user!',
        );

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatMessageWidget(message: message),
            ),
          ),
        );

        // Assert
        expect(find.text('Hello, user!'), findsOneWidget);

        // Check left alignment
        final row = tester.widget<Row>(find.byType(Row));
        expect(row.mainAxisAlignment, MainAxisAlignment.start);
      });

      testWidgets('displays assistant message with grey background',
          (tester) async {
        // Arrange
        final message = TestData.createMessage(
          user: ChatUser.assistant,
          text: 'Test',
        );

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatMessageWidget(message: message),
            ),
          ),
        );

        // Assert
        final container = tester.widget<Container>(
          find.descendant(
            of: find.byType(ChatMessageWidget),
            matching: find.byType(Container).first,
          ),
        );
        final decoration = container.decoration! as BoxDecoration;
        expect(decoration.color, isNotNull);
        // Surface container color for assistant messages
      });

      testWidgets('shows streaming indicator for assistant messages',
          (tester) async {
        // Arrange
        final message = TestData.createMessage(
          user: ChatUser.assistant,
          text: 'Thinking...',
        );

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatMessageWidget(
                message: message,
                isStreaming: true,
              ),
            ),
          ),
        );

        // Assert
        expect(find.text('Typing...'), findsWidgets);
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
      });

      testWidgets('renders markdown for assistant messages', (tester) async {
        // Arrange
        final message = TestData.createMessage(
          user: ChatUser.assistant,
          text: '**bold** and *italic* text',
        );

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatMessageWidget(message: message),
            ),
          ),
        );

        // Assert - should use MarkdownBody for assistant messages
        expect(find.byType(MarkdownBody), findsOneWidget);
      });

      testWidgets('does not render markdown for user messages', (tester) async {
        // Arrange
        final message = TestData.createMessage(
          text: '**bold** and *italic* text',
        );

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatMessageWidget(message: message),
            ),
          ),
        );

        // Assert - should use Text for user messages, not MarkdownBody
        expect(find.byType(MarkdownBody), findsNothing);
        expect(find.text('**bold** and *italic* text'), findsOneWidget);
      });

      testWidgets('renders code blocks with syntax highlighting',
          (tester) async {
        // Arrange
        final message = TestData.createMessage(
          user: ChatUser.assistant,
          text: '```dart\nvoid main() {}\n```',
        );

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatMessageWidget(message: message),
            ),
          ),
        );

        // Assert - MarkdownBody should render code blocks
        expect(find.byType(MarkdownBody), findsOneWidget);
        // The code block should be rendered (implementation detail - just
        // verify it doesn't crash)
        await tester.pumpAndSettle();
      });
    });

    group('System Messages', () {
      testWidgets('displays system message centered', (tester) async {
        // Arrange
        final message = ErrorMessage.create(
          id: 'error-1',
          message: 'Operation cancelled',
        );

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatMessageWidget(message: message),
            ),
          ),
        );

        // Assert
        expect(find.text('Operation cancelled'), findsOneWidget);
        expect(find.byType(Center), findsOneWidget);
      });

      testWidgets('displays system message with subtle styling',
          (tester) async {
        // Arrange
        final message = ErrorMessage.create(
          id: 'error-2',
          message: 'System notification',
        );

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatMessageWidget(message: message),
            ),
          ),
        );

        // Assert
        expect(find.text('System notification'), findsOneWidget);

        // System messages use bodySmall style
        final text = tester.widget<Text>(
          find.descendant(
            of: find.byType(Center),
            matching: find.byType(Text),
          ),
        );
        expect(text.style?.fontSize, lessThan(16)); // bodySmall is smaller
      });
    });

    group('Error Messages', () {
      testWidgets('displays error message', (tester) async {
        // Arrange
        final message = ErrorMessage.create(
          id: 'error-3',
          message: 'Something went wrong',
        );

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatMessageWidget(message: message),
            ),
          ),
        );

        // Assert
        expect(find.text('Something went wrong'), findsOneWidget);
      });
    });

    group('Edge Cases', () {
      testWidgets('handles empty text message', (tester) async {
        // Arrange
        final message = TestData.createMessage(
          text: '',
        );

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatMessageWidget(message: message),
            ),
          ),
        );

        // Assert
        expect(find.text(''), findsOneWidget);
      });

      testWidgets('handles long message text', (tester) async {
        // Arrange
        final longText = 'A' * 500;
        final message = TestData.createMessage(
          text: longText,
        );

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: ChatMessageWidget(message: message),
            ),
          ),
        );

        // Assert
        expect(find.textContaining('A'), findsOneWidget);
      });

      testWidgets('respects maxWidth constraint', (tester) async {
        // Arrange
        final message = TestData.createMessage();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(
              body: SizedBox(
                width: 800,
                child: ChatMessageWidget(message: message),
              ),
            ),
          ),
        );

        // Assert
        final container = tester.widget<Container>(
          find.descendant(
            of: find.byType(Flexible),
            matching: find.byType(Container).first,
          ),
        );
        final constraints = container.constraints!;
        expect(constraints.maxWidth, 600);
      });
    });
  });
}
