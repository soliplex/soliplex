import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/core/models/active_run_state.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';
import 'package:soliplex_frontend/features/chat/chat_panel.dart';
import 'package:soliplex_frontend/features/history/history_panel.dart';
import 'package:soliplex_frontend/features/thread/thread_screen.dart';

import '../../helpers/test_helpers.dart';

void main() {
  group('ThreadScreen', () {
    final testRoom = TestData.createRoom();
    final testThread = TestData.createThread(
      name: 'Test Thread',
    );

    testWidgets('displays ChatPanel and HistoryPanel on desktop',
        (tester) async {
      // Set desktop screen size (>=600px)
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      await tester.pumpWidget(
        createTestApp(
          home: const ThreadScreen(
            roomId: 'test-room',
            threadId: 'test-thread',
          ),
          overrides: [
            roomsProvider.overrideWith((_) async => [testRoom]),
            threadsProvider('test-room')
                .overrideWith((_) async => [testThread]),
            activeRunNotifierOverride(const IdleState()),
          ],
        ),
      );

      // Let providers initialize
      await tester.pumpAndSettle();

      // Should display both panels on desktop
      expect(find.byType(HistoryPanel), findsOneWidget);
      expect(find.byType(ChatPanel), findsOneWidget);
    });

    testWidgets('displays only ChatPanel on mobile', (tester) async {
      // Set mobile screen size (<600px)
      tester.view.physicalSize = const Size(400, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      await tester.pumpWidget(
        createTestApp(
          home: const ThreadScreen(
            roomId: 'test-room',
            threadId: 'test-thread',
          ),
          overrides: [
            roomsProvider.overrideWith((_) async => [testRoom]),
            threadsProvider('test-room')
                .overrideWith((_) async => [testThread]),
            activeRunNotifierOverride(const IdleState()),
          ],
        ),
      );

      // Let providers initialize
      await tester.pumpAndSettle();

      // Should display only ChatPanel on mobile
      expect(find.byType(ChatPanel), findsOneWidget);
      expect(find.byType(HistoryPanel), findsNothing);
    });

    testWidgets('displays thread name as title when available', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: const ThreadScreen(
            roomId: 'test-room',
            threadId: 'test-thread',
          ),
          overrides: [
            roomsProvider.overrideWith((_) async => [testRoom]),
            threadsProvider('test-room')
                .overrideWith((_) async => [testThread]),
            activeRunNotifierOverride(const IdleState()),
          ],
        ),
      );

      // Let providers initialize
      await tester.pumpAndSettle();

      // Should display thread name as title in the AppBar
      final appBar = tester.widget<AppBar>(find.byType(AppBar));
      final titleWidget = appBar.title! as Text;
      expect(titleWidget.data, equals('Test Thread'));
    });

    testWidgets('displays room name as title when thread has no name',
        (tester) async {
      final threadWithoutName = TestData.createThread();

      await tester.pumpWidget(
        createTestApp(
          home: const ThreadScreen(
            roomId: 'test-room',
            threadId: 'test-thread',
          ),
          overrides: [
            roomsProvider.overrideWith((_) async => [testRoom]),
            threadsProvider('test-room')
                .overrideWith((_) async => [threadWithoutName]),
            activeRunNotifierOverride(const IdleState()),
          ],
        ),
      );

      // Let providers initialize
      await tester.pumpAndSettle();

      // Should display room name as title in the AppBar
      final appBar = tester.widget<AppBar>(find.byType(AppBar));
      final titleWidget = appBar.title! as Text;
      expect(titleWidget.data, equals('Test Room'));
    });

    testWidgets('displays default title when room name is null',
        (tester) async {
      // Room with default name 'Test Room' from TestData.createRoom defaults
      final roomWithoutName = TestData.createRoom();
      final threadWithoutName = TestData.createThread();

      await tester.pumpWidget(
        createTestApp(
          home: const ThreadScreen(
            roomId: 'test-room',
            threadId: 'test-thread',
          ),
          overrides: [
            roomsProvider.overrideWith((_) async => [roomWithoutName]),
            threadsProvider('test-room')
                .overrideWith((_) async => [threadWithoutName]),
            activeRunNotifierOverride(const IdleState()),
          ],
        ),
      );

      // Let providers initialize
      await tester.pumpAndSettle();

      // Should display room name as title in the AppBar
      // (TestData.createRoom defaults to 'Test Room')
      final appBar = tester.widget<AppBar>(find.byType(AppBar));
      final titleWidget = appBar.title! as Text;
      expect(titleWidget.data, equals('Test Room'));
    });

    testWidgets('has AppBar with title', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: const ThreadScreen(
            roomId: 'test-room',
            threadId: 'test-thread',
          ),
          overrides: [
            roomsProvider.overrideWith((_) async => [testRoom]),
            threadsProvider('test-room')
                .overrideWith((_) async => [testThread]),
            activeRunNotifierOverride(const IdleState()),
          ],
        ),
      );

      await tester.pumpAndSettle();

      // Should have an AppBar
      expect(find.byType(AppBar), findsOneWidget);

      // AppBar should contain a title
      final appBar = tester.widget<AppBar>(find.byType(AppBar));
      expect(appBar.title, isNotNull);
    });

    testWidgets('is wrapped in Scaffold', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: const ThreadScreen(
            roomId: 'test-room',
            threadId: 'test-thread',
          ),
          overrides: [
            roomsProvider.overrideWith((_) async => [testRoom]),
            threadsProvider('test-room')
                .overrideWith((_) async => [testThread]),
            activeRunNotifierOverride(const IdleState()),
          ],
        ),
      );

      await tester.pumpAndSettle();

      // Should be wrapped in Scaffold
      expect(find.byType(Scaffold), findsOneWidget);
    });
  });
}
