import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/core/models/active_run_state.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';
import 'package:soliplex_frontend/features/chat/chat_panel.dart';
import 'package:soliplex_frontend/features/chat/widgets/chat_input.dart';
import 'package:soliplex_frontend/features/chat/widgets/message_list.dart';
import 'package:soliplex_frontend/shared/widgets/error_display.dart';

import '../../helpers/test_helpers.dart';

void main() {
  group('ChatPanel', () {
    group('Layout', () {
      testWidgets('displays message list and chat input', (tester) async {
        // Arrange
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: ChatPanel(),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => null),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Assert
        expect(find.byType(MessageList), findsOneWidget);
        expect(find.byType(ChatInput), findsOneWidget);
      });

      testWidgets('message list is expanded', (tester) async {
        // Arrange
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: ChatPanel(),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => null),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Assert - MessageList should be wrapped in an Expanded widget
        final messageListFinder = find.byType(MessageList);
        expect(messageListFinder, findsOneWidget);

        // Find the Expanded widget that contains MessageList
        final expandedFinder = find.ancestor(
          of: messageListFinder,
          matching: find.byType(Expanded),
        );
        expect(expandedFinder, findsOneWidget);
      });

      testWidgets('chat input is at bottom', (tester) async {
        // Arrange
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: ChatPanel(),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => null),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Assert
        expect(find.byType(ChatInput), findsOneWidget);
      });
    });

    group('Streaming State', () {
      testWidgets('shows cancel button when streaming', (tester) async {
        // Arrange
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: ChatPanel(),
            ),
            overrides: [
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
        expect(find.text('Streaming response...'), findsOneWidget);
        expect(find.text('Cancel'), findsOneWidget);
      });

      testWidgets('does not show cancel button when idle', (tester) async {
        // Arrange
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: ChatPanel(),
            ),
            overrides: [
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Assert
        expect(find.text('Streaming response...'), findsNothing);
        expect(find.text('Cancel'), findsNothing);
      });
    });

    group('Error State', () {
      testWidgets('shows error display when run has error', (tester) async {
        // Arrange
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: ChatPanel(),
            ),
            overrides: [
              activeRunNotifierOverride(
                const CompletedState(
                  threadId: '',
                  runId: '',
                  context: RunContext.empty,
                  result: Failed(errorMessage: 'Something went wrong'),
                ),
              ),
            ],
          ),
        );

        // Assert
        expect(find.byType(ErrorDisplay), findsOneWidget);
        expect(find.text('Something went wrong'), findsOneWidget);
      });

      testWidgets('shows message list when no error', (tester) async {
        // Arrange
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: ChatPanel(),
            ),
            overrides: [
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Assert
        expect(find.byType(MessageList), findsOneWidget);
        expect(find.byType(ErrorDisplay), findsNothing);
      });
    });

    group('Input State', () {
      testWidgets('input disabled when no room selected', (tester) async {
        // Arrange
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: ChatPanel(),
            ),
            overrides: [
              currentRoomProvider.overrideWith((ref) => null),
              currentThreadProvider.overrideWith((ref) => null),
              threadSelectionProviderOverride(const NoThreadSelected()),
              activeRunNotifierOverride(const IdleState()),
            ],
          ),
        );

        // Assert
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(textField.enabled, isFalse);
      });

      testWidgets('input enabled when room selected', (tester) async {
        // Arrange
        final mockRoom = TestData.createRoom();
        final mockThread = TestData.createThread();

        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: ChatPanel(),
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
        expect(textField.enabled, isTrue);
      });
    });
  });
}
