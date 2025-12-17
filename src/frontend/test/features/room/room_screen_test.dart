import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';
import 'package:soliplex_frontend/features/room/room_screen.dart';
import 'package:soliplex_frontend/shared/widgets/empty_state.dart';
import 'package:soliplex_frontend/shared/widgets/loading_indicator.dart';

import '../../helpers/test_helpers.dart';

void main() {
  group('RoomScreen', () {
    testWidgets('displays loading indicator while fetching', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'general'),
        ),
      );

      expect(find.byType(LoadingIndicator), findsOneWidget);

      await tester.pumpAndSettle();
    });

    testWidgets('displays thread list when loaded', (tester) async {
      final mockThreads = [
        TestData.createThread(
          id: 'thread1',
          roomId: 'general',
          name: 'Thread 1',
        ),
        TestData.createThread(
          id: 'thread2',
          roomId: 'general',
          name: 'Thread 2',
        ),
      ];

      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'general'),
          overrides: [
            threadsProvider('general').overrideWith((ref) async => mockThreads),
          ],
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Thread 1'), findsOneWidget);
      expect(find.text('Thread 2'), findsOneWidget);
    });

    testWidgets('displays empty state when no threads', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'empty-room'),
          overrides: [
            threadsProvider('empty-room').overrideWith((ref) async => []),
          ],
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byType(EmptyState), findsOneWidget);
      expect(find.text('No threads in this room'), findsOneWidget);
    });

    testWidgets('shows FAB for creating thread', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'general'),
          overrides: [
            threadsProvider('general').overrideWith((ref) async => []),
          ],
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byType(FloatingActionButton), findsOneWidget);
    });
  });
}
