import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';
import 'package:soliplex_frontend/features/chat/chat_panel.dart';
import 'package:soliplex_frontend/features/history/history_panel.dart';
import 'package:soliplex_frontend/features/room/room_screen.dart';

import '../../helpers/test_helpers.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('RoomScreen layout', () {
    testWidgets('shows desktop layout with sidebar on wide screens',
        (tester) async {
      tester.view.physicalSize = const Size(800, 600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.resetPhysicalSize());

      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'general'),
          overrides: [
            threadsProvider('general').overrideWith((ref) async => []),
            lastViewedThreadProvider('general')
                .overrideWith((ref) async => const NoLastViewed()),
          ],
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byType(HistoryPanel), findsOneWidget);
      expect(find.byType(ChatPanel), findsOneWidget);
    });

    testWidgets('shows mobile layout without sidebar on narrow screens',
        (tester) async {
      tester.view.physicalSize = const Size(400, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.resetPhysicalSize());

      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'general'),
          overrides: [
            threadsProvider('general').overrideWith((ref) async => []),
            lastViewedThreadProvider('general')
                .overrideWith((ref) async => const NoLastViewed()),
          ],
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byType(ChatPanel), findsOneWidget);
      expect(find.byType(HistoryPanel), findsNothing);
    });

    testWidgets('shows FAB for creating thread', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'general'),
          overrides: [
            threadsProvider('general').overrideWith((ref) async => []),
            lastViewedThreadProvider('general')
                .overrideWith((ref) async => const NoLastViewed()),
          ],
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byType(FloatingActionButton), findsOneWidget);
    });
  });

  group('RoomScreen sidebar toggle', () {
    testWidgets('toggle button hides sidebar on desktop', (tester) async {
      tester.view.physicalSize = const Size(800, 600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.resetPhysicalSize());

      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'general'),
          overrides: [
            threadsProvider('general').overrideWith((ref) async => []),
            lastViewedThreadProvider('general')
                .overrideWith((ref) async => const NoLastViewed()),
          ],
        ),
      );

      await tester.pumpAndSettle();

      // Initially sidebar visible
      expect(find.byType(HistoryPanel), findsOneWidget);
      expect(find.byIcon(Icons.menu_open), findsOneWidget);

      // Tap toggle to hide
      await tester.tap(find.byIcon(Icons.menu_open));
      await tester.pumpAndSettle();

      // Sidebar hidden
      expect(find.byType(HistoryPanel), findsNothing);
      expect(find.byIcon(Icons.menu), findsOneWidget);
    });

    testWidgets('toggle button shows sidebar after hiding', (tester) async {
      tester.view.physicalSize = const Size(800, 600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.resetPhysicalSize());

      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'general'),
          overrides: [
            threadsProvider('general').overrideWith((ref) async => []),
            lastViewedThreadProvider('general')
                .overrideWith((ref) async => const NoLastViewed()),
          ],
        ),
      );

      await tester.pumpAndSettle();

      // Hide sidebar
      await tester.tap(find.byIcon(Icons.menu_open));
      await tester.pumpAndSettle();

      // Show sidebar again
      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      expect(find.byType(HistoryPanel), findsOneWidget);
      expect(find.byIcon(Icons.menu_open), findsOneWidget);
    });
  });

  group('RoomScreen thread selection', () {
    testWidgets('selects thread from query param', (tester) async {
      final mockThreads = [
        TestData.createThread(id: 'thread-1', roomId: 'general'),
        TestData.createThread(id: 'thread-2', roomId: 'general'),
      ];

      late ProviderContainer container;
      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(
            roomId: 'general',
            initialThreadId: 'thread-2',
          ),
          overrides: [
            threadsProvider('general').overrideWith((ref) async => mockThreads),
            lastViewedThreadProvider('general')
                .overrideWith((ref) async => const HasLastViewed('thread-1')),
          ],
          onContainerCreated: (c) => container = c,
        ),
      );

      await tester.pumpAndSettle();

      // Should select thread-2 from query param, not last viewed thread-1
      final selection = container.read(threadSelectionProvider);
      expect(selection, isA<ThreadSelected>());
      expect((selection as ThreadSelected).threadId, equals('thread-2'));
    });

    testWidgets('falls back to last viewed thread', (tester) async {
      final mockThreads = [
        TestData.createThread(id: 'thread-1', roomId: 'general'),
        TestData.createThread(id: 'thread-2', roomId: 'general'),
      ];

      late ProviderContainer container;
      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'general'),
          overrides: [
            threadsProvider('general').overrideWith((ref) async => mockThreads),
            lastViewedThreadProvider('general')
                .overrideWith((ref) async => const HasLastViewed('thread-2')),
          ],
          onContainerCreated: (c) => container = c,
        ),
      );

      await tester.pumpAndSettle();

      // Should select last viewed thread-2
      final selection = container.read(threadSelectionProvider);
      expect(selection, isA<ThreadSelected>());
      expect((selection as ThreadSelected).threadId, equals('thread-2'));
    });

    testWidgets('falls back to first thread when no last viewed',
        (tester) async {
      final mockThreads = [
        TestData.createThread(id: 'thread-1', roomId: 'general'),
        TestData.createThread(id: 'thread-2', roomId: 'general'),
      ];

      late ProviderContainer container;
      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'general'),
          overrides: [
            threadsProvider('general').overrideWith((ref) async => mockThreads),
            lastViewedThreadProvider('general')
                .overrideWith((ref) async => const NoLastViewed()),
          ],
          onContainerCreated: (c) => container = c,
        ),
      );

      await tester.pumpAndSettle();

      // Should select first thread
      final selection = container.read(threadSelectionProvider);
      expect(selection, isA<ThreadSelected>());
      expect((selection as ThreadSelected).threadId, equals('thread-1'));
    });

    testWidgets('sets NoThreadSelected when room is empty', (tester) async {
      late ProviderContainer container;
      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'empty-room'),
          overrides: [
            threadsProvider('empty-room').overrideWith((ref) async => []),
            lastViewedThreadProvider('empty-room')
                .overrideWith((ref) async => const NoLastViewed()),
          ],
          onContainerCreated: (c) => container = c,
        ),
      );

      await tester.pumpAndSettle();

      final selection = container.read(threadSelectionProvider);
      expect(selection, isA<NoThreadSelected>());
    });

    testWidgets('ignores invalid query param and falls back to first thread',
        (tester) async {
      final mockThreads = [
        TestData.createThread(id: 'thread-1', roomId: 'general'),
        TestData.createThread(id: 'thread-2', roomId: 'general'),
      ];

      late ProviderContainer container;
      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(
            roomId: 'general',
            initialThreadId: 'nonexistent-thread',
          ),
          overrides: [
            threadsProvider('general').overrideWith((ref) async => mockThreads),
            lastViewedThreadProvider('general')
                .overrideWith((ref) async => const NoLastViewed()),
          ],
          onContainerCreated: (c) => container = c,
        ),
      );

      await tester.pumpAndSettle();

      // Should ignore invalid query param and fall back to first thread
      final selection = container.read(threadSelectionProvider);
      expect(selection, isA<ThreadSelected>());
      expect((selection as ThreadSelected).threadId, equals('thread-1'));
    });
  });

  group('RoomScreen room ID sync', () {
    testWidgets('syncs currentRoomIdProvider on initialization',
        (tester) async {
      final mockThreads = [
        TestData.createThread(id: 'thread-1', roomId: 'room-abc'),
      ];

      late ProviderContainer container;
      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'room-abc'),
          overrides: [
            threadsProvider('room-abc')
                .overrideWith((ref) async => mockThreads),
            lastViewedThreadProvider('room-abc')
                .overrideWith((ref) async => const NoLastViewed()),
          ],
          onContainerCreated: (c) => container = c,
        ),
      );

      await tester.pumpAndSettle();

      // currentRoomIdProvider should be synced with widget.roomId
      final roomId = container.read(currentRoomIdProvider);
      expect(roomId, equals('room-abc'));
    });

    testWidgets('updates currentRoomIdProvider when room changes',
        (tester) async {
      final roomAThreads = [
        TestData.createThread(id: 'thread-a', roomId: 'room-a'),
      ];
      final roomBThreads = [
        TestData.createThread(id: 'thread-b', roomId: 'room-b'),
      ];

      late ProviderContainer container;

      // Start with room-a
      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'room-a'),
          overrides: [
            threadsProvider('room-a').overrideWith((ref) async => roomAThreads),
            threadsProvider('room-b').overrideWith((ref) async => roomBThreads),
            lastViewedThreadProvider('room-a')
                .overrideWith((ref) async => const NoLastViewed()),
            lastViewedThreadProvider('room-b')
                .overrideWith((ref) async => const NoLastViewed()),
          ],
          onContainerCreated: (c) => container = c,
        ),
      );

      await tester.pumpAndSettle();
      expect(container.read(currentRoomIdProvider), equals('room-a'));

      // Navigate to room-b by rebuilding with different roomId
      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'room-b'),
          overrides: [
            threadsProvider('room-a').overrideWith((ref) async => roomAThreads),
            threadsProvider('room-b').overrideWith((ref) async => roomBThreads),
            lastViewedThreadProvider('room-a')
                .overrideWith((ref) async => const NoLastViewed()),
            lastViewedThreadProvider('room-b')
                .overrideWith((ref) async => const NoLastViewed()),
          ],
          onContainerCreated: (c) => container = c,
        ),
      );

      await tester.pumpAndSettle();

      // currentRoomIdProvider should now be room-b
      expect(container.read(currentRoomIdProvider), equals('room-b'));
    });
  });

  group('RoomScreen room dropdown', () {
    testWidgets('shows room dropdown', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'general'),
          overrides: [
            threadsProvider('general').overrideWith((ref) async => []),
            lastViewedThreadProvider('general')
                .overrideWith((ref) async => const NoLastViewed()),
            roomsProvider.overrideWith(
              (ref) async => [
                TestData.createRoom(id: 'general', name: 'General'),
                TestData.createRoom(id: 'support', name: 'Support'),
              ],
            ),
          ],
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byType(DropdownMenu<String>), findsOneWidget);
    });
  });
}
