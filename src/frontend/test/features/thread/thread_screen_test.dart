import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/core/models/active_run_state.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';
import 'package:soliplex_frontend/features/chat/chat_panel.dart';
import 'package:soliplex_frontend/features/history/history_panel.dart';
import 'package:soliplex_frontend/features/inspector/http_inspector_panel.dart';
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

    group('HTTP Inspector drawer', () {
      testWidgets('has inspector toggle button in app bar', (tester) async {
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

        // Should have inspector toggle button with bug icon
        expect(find.byIcon(Icons.bug_report), findsOneWidget);
      });

      testWidgets('tapping toggle opens inspector drawer', (tester) async {
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

        // Inspector panel should not be visible initially
        expect(find.byType(HttpInspectorPanel), findsNothing);

        // Tap the inspector toggle button
        await tester.tap(find.byIcon(Icons.bug_report));
        await tester.pumpAndSettle();

        // Inspector panel should now be visible
        expect(find.byType(HttpInspectorPanel), findsOneWidget);
      });

      testWidgets('drawer can be closed by tapping scrim', (tester) async {
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

        // Open the drawer
        await tester.tap(find.byIcon(Icons.bug_report));
        await tester.pumpAndSettle();

        expect(find.byType(HttpInspectorPanel), findsOneWidget);

        // Tap on the scrim (left side of screen) to close
        await tester.tapAt(const Offset(10, 300));
        await tester.pumpAndSettle();

        // Drawer should be closed
        expect(find.byType(HttpInspectorPanel), findsNothing);
      });
    });
  });
}
