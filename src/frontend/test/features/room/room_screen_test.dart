import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';
import 'package:soliplex_frontend/features/chat/chat_panel.dart';
import 'package:soliplex_frontend/features/history/history_panel.dart';
import 'package:soliplex_frontend/features/room/room_screen.dart';

import '../../helpers/test_helpers.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('RoomScreen', () {
    testWidgets('shows desktop layout with sidebar on wide screens',
        (tester) async {
      // Set desktop size (>= 600)
      tester.view.physicalSize = const Size(800, 600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.resetPhysicalSize());

      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'general'),
          overrides: [
            threadsProvider('general').overrideWith((ref) async => []),
            lastViewedThreadProvider('general')
                .overrideWith((ref) async => null),
          ],
        ),
      );

      await tester.pumpAndSettle();

      // Desktop: HistoryPanel visible in sidebar
      expect(find.byType(HistoryPanel), findsOneWidget);
      expect(find.byType(ChatPanel), findsOneWidget);
    });

    testWidgets('shows mobile layout without sidebar on narrow screens',
        (tester) async {
      // Set mobile size (< 600)
      tester.view.physicalSize = const Size(400, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.resetPhysicalSize());

      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'general'),
          overrides: [
            threadsProvider('general').overrideWith((ref) async => []),
            lastViewedThreadProvider('general')
                .overrideWith((ref) async => null),
          ],
        ),
      );

      await tester.pumpAndSettle();

      // Mobile: Only ChatPanel visible (HistoryPanel in drawer, not rendered)
      expect(find.byType(ChatPanel), findsOneWidget);
      // HistoryPanel is in drawer, not rendered until drawer opens
      expect(find.byType(HistoryPanel), findsNothing);
    });

    testWidgets('shows FAB for creating thread', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: const RoomScreen(roomId: 'general'),
          overrides: [
            threadsProvider('general').overrideWith((ref) async => []),
            lastViewedThreadProvider('general')
                .overrideWith((ref) async => null),
          ],
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byType(FloatingActionButton), findsOneWidget);
    });
  });
}
