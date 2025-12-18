import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/models/active_run_state.dart';
import 'package:soliplex_frontend/core/providers/active_run_provider.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';
import 'package:soliplex_frontend/features/chat/widgets/chat_message_widget.dart';
import 'package:soliplex_frontend/features/chat/widgets/message_list.dart';
import 'package:soliplex_frontend/shared/widgets/empty_state.dart';

import '../../../helpers/test_helpers.dart';

void main() {
  group('MessageList', () {
    group('Empty State', () {
      testWidgets('displays empty state when no messages', (tester) async {
        // Arrange
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: MessageList(),
            ),
            overrides: [
              currentThreadProvider.overrideWith((ref) => null),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Assert
        expect(find.byType(EmptyState), findsOneWidget);
        expect(
          find.text('No messages yet. Send one below!'),
          findsOneWidget,
        );
      });

      testWidgets('shows chat bubble icon in empty state', (tester) async {
        // Arrange
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: MessageList(),
            ),
            overrides: [
              currentThreadProvider.overrideWith((ref) => null),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Assert
        expect(find.byIcon(Icons.chat_bubble_outline), findsOneWidget);
      });
    });

    group('Message Display', () {
      testWidgets('displays list of messages', (tester) async {
        // Arrange
        final messages = [
          TestData.createMessage(
            id: 'msg-1',
            text: 'Hello',
          ),
          TestData.createMessage(
            id: 'msg-2',
            user: ChatUser.assistant,
            text: 'Hi there!',
          ),
          TestData.createMessage(
            id: 'msg-3',
            text: 'How are you?',
          ),
        ];

        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: MessageList(),
            ),
            overrides: [
              currentThreadProvider.overrideWith((ref) => mockThread),
              threadMessagesProvider(mockThread.id)
                  .overrideWith((ref) => messages),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Assert
        expect(find.byType(ChatMessageWidget), findsNWidgets(3));
        expect(find.text('Hello'), findsOneWidget);
        expect(find.text('Hi there!'), findsOneWidget);
        expect(find.text('How are you?'), findsOneWidget);
      });

      testWidgets('uses ListView.builder', (tester) async {
        // Arrange
        final messages = [
          TestData.createMessage(id: 'msg-1', text: 'Message 1'),
          TestData.createMessage(id: 'msg-2', text: 'Message 2'),
        ];

        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: MessageList(),
            ),
            overrides: [
              currentThreadProvider.overrideWith((ref) => mockThread),
              threadMessagesProvider(mockThread.id)
                  .overrideWith((ref) => messages),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Assert
        expect(find.byType(ListView), findsOneWidget);
      });

      testWidgets('assigns unique keys to message widgets', (tester) async {
        // Arrange
        final messages = [
          TestData.createMessage(id: 'msg-1', text: 'Message 1'),
          TestData.createMessage(id: 'msg-2', text: 'Message 2'),
        ];

        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: MessageList(),
            ),
            overrides: [
              currentThreadProvider.overrideWith((ref) => mockThread),
              threadMessagesProvider(mockThread.id)
                  .overrideWith((ref) => messages),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Assert
        final messageWidgets = tester.widgetList<ChatMessageWidget>(
          find.byType(ChatMessageWidget),
        );
        expect(messageWidgets.first.key, isA<ValueKey<String>>());
        expect(messageWidgets.last.key, isA<ValueKey<String>>());
      });
    });

    group('Streaming Indicator', () {
      testWidgets('shows activity indicator when streaming', (tester) async {
        // Arrange
        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: MessageList(),
            ),
            overrides: [
              currentThreadProvider.overrideWith((ref) => mockThread),
              threadMessagesProvider(mockThread.id).overrideWith((ref) => []),
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

        // Assert
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
        expect(find.text('Assistant is thinking...'), findsOneWidget);
      });

      testWidgets('does not show indicator when not streaming', (tester) async {
        // Arrange
        final messages = [
          TestData.createMessage(text: 'Hello'),
        ];

        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: MessageList(),
            ),
            overrides: [
              currentThreadProvider.overrideWith((ref) => mockThread),
              threadMessagesProvider(mockThread.id)
                  .overrideWith((ref) => messages),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Assert
        expect(find.text('Assistant is thinking...'), findsNothing);
      });

      testWidgets('shows indicator at bottom of list', (tester) async {
        // Arrange
        final messages = [
          TestData.createMessage(id: 'msg-1', text: 'Message 1'),
          TestData.createMessage(id: 'msg-2', text: 'Message 2'),
        ];

        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: MessageList(),
            ),
            overrides: [
              currentThreadProvider.overrideWith((ref) => mockThread),
              threadMessagesProvider(mockThread.id)
                  .overrideWith((ref) => messages),
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

        // Assert
        // Should have 2 messages + 1 indicator
        expect(find.byType(ChatMessageWidget), findsNWidgets(2));
        expect(find.text('Assistant is thinking...'), findsOneWidget);
      });
    });

    group('Streaming Status', () {
      testWidgets('passes isStreaming to message being streamed',
          (tester) async {
        // Arrange
        final messages = [
          TestData.createMessage(id: 'msg-1', text: 'Complete message'),
        ];

        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: MessageList(),
            ),
            overrides: [
              currentThreadProvider.overrideWith((ref) => mockThread),
              // Don't provide duplicate messages in threadMessagesProvider
              // since they're already in activeRunNotifierProvider.messages
              threadMessagesProvider(mockThread.id).overrideWith((ref) => []),
              activeRunNotifierOverride(
                RunningState(
                  threadId: 'test-thread',
                  runId: 'test-run',
                  context: RunContext(messages: messages),
                  textStreaming: const Streaming(
                    messageId: 'msg-1',
                    text: 'Typing...',
                  ),
                ),
              ),
            ],
          ),
        );

        // Assert
        // Now there should be only one message widget
        final messageWidget = tester.widget<ChatMessageWidget>(
          find.byType(ChatMessageWidget),
        );
        expect(messageWidget.isStreaming, isTrue);
      });

      testWidgets('does not pass isStreaming to other messages',
          (tester) async {
        // Arrange
        final messages = [
          TestData.createMessage(id: 'msg-1', text: 'Old message'),
          TestData.createMessage(id: 'msg-2', text: 'Current message'),
        ];

        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: MessageList(),
            ),
            overrides: [
              currentThreadProvider.overrideWith((ref) => mockThread),
              // Don't provide duplicate messages in threadMessagesProvider
              // since they're already in activeRunNotifierProvider.messages
              threadMessagesProvider(mockThread.id).overrideWith((ref) => []),
              activeRunNotifierOverride(
                RunningState(
                  threadId: 'test-thread',
                  runId: 'test-run',
                  context: RunContext(messages: messages),
                  textStreaming: const Streaming(
                    messageId: 'msg-2',
                    text: 'Typing...',
                  ),
                ),
              ),
            ],
          ),
        );

        // Assert
        final messageWidgets = tester.widgetList<ChatMessageWidget>(
          find.byType(ChatMessageWidget),
        );
        expect(messageWidgets.first.isStreaming, isFalse);
        expect(messageWidgets.last.isStreaming, isTrue);
      });
    });

    group('Scrolling', () {
      testWidgets('uses ScrollController', (tester) async {
        // Arrange
        final messages = [
          TestData.createMessage(text: 'Message 1'),
        ];

        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: MessageList(),
            ),
            overrides: [
              currentThreadProvider.overrideWith((ref) => mockThread),
              threadMessagesProvider(mockThread.id)
                  .overrideWith((ref) => messages),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Assert
        final listView = tester.widget<ListView>(find.byType(ListView));
        expect(listView.controller, isNotNull);
      });

      testWidgets('scrolls to bottom when new messages arrive', (tester) async {
        // Arrange
        final initialMessages = [
          TestData.createMessage(id: 'msg-1', text: 'Message 1'),
        ];

        final updatedMessages = [
          TestData.createMessage(id: 'msg-1', text: 'Message 1'),
          TestData.createMessage(id: 'msg-2', text: 'Message 2'),
          TestData.createMessage(id: 'msg-3', text: 'Message 3'),
        ];

        final mockThread = TestData.createThread();

        // Use a flag to track which messages to return
        // Riverpod 3.0 uses == for update filtering, so we need different
        // list instances (not a mutated list) to trigger rebuilds
        var useUpdatedMessages = false;

        final container = ProviderContainer(
          overrides: [
            currentThreadProvider.overrideWith((ref) => mockThread),
            allMessagesProvider.overrideWith((ref) {
              return useUpdatedMessages ? updatedMessages : initialMessages;
            }),
            activeRunNotifierOverride(const IdleState()),
          ],
        );
        addTearDown(container.dispose);

        // Act - Initial render
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: const MaterialApp(
              home: Scaffold(
                body: MessageList(),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();

        expect(find.text('Message 1'), findsOneWidget);
        expect(find.text('Message 3'), findsNothing);

        // Update to use new messages and invalidate the provider
        useUpdatedMessages = true;
        container.invalidate(allMessagesProvider);

        await tester.pumpAndSettle();

        // Assert - Should have scrolled (no assertion for exact position,
        // just verify no exceptions)
        expect(find.text('Message 3'), findsOneWidget);
      });
    });

    group('Edge Cases', () {
      testWidgets('handles single message', (tester) async {
        // Arrange
        final messages = [
          TestData.createMessage(text: 'Only message'),
        ];

        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: MessageList(),
            ),
            overrides: [
              currentThreadProvider.overrideWith((ref) => mockThread),
              threadMessagesProvider(mockThread.id)
                  .overrideWith((ref) => messages),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Assert
        expect(find.byType(ChatMessageWidget), findsOneWidget);
        expect(find.text('Only message'), findsOneWidget);
      });

      testWidgets('handles many messages', (tester) async {
        // Arrange
        final messages = List.generate(
          50,
          (index) => TestData.createMessage(
            id: 'msg-$index',
            text: 'Message $index',
          ),
        );

        final mockThread = TestData.createThread();

        // Act
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: MessageList(),
            ),
            overrides: [
              currentThreadProvider.overrideWith((ref) => mockThread),
              threadMessagesProvider(mockThread.id)
                  .overrideWith((ref) => messages),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        await tester.pumpAndSettle();

        // Assert - ListView should handle many items efficiently
        expect(find.byType(ListView), findsOneWidget);
      });
    });
  });
}
