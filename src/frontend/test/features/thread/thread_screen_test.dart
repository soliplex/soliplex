import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/features/thread/thread_screen.dart';

import '../../helpers/test_helpers.dart';

void main() {
  group('ThreadScreen', () {
    testWidgets('displays placeholder message', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: const ThreadScreen(
            roomId: 'room-1',
            threadId: 'thread-1',
          ),
        ),
      );

      expect(find.text('Chat UI - Coming in AM3'), findsOneWidget);
    });

    testWidgets('displays room and thread IDs', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: const ThreadScreen(
            roomId: 'test-room',
            threadId: 'test-thread',
          ),
        ),
      );

      expect(find.textContaining('test-room'), findsOneWidget);
      expect(find.textContaining('test-thread'), findsOneWidget);
    });

    testWidgets('displays chat icon', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: const ThreadScreen(
            roomId: 'room-1',
            threadId: 'thread-1',
          ),
        ),
      );

      expect(find.byIcon(Icons.chat), findsOneWidget);
    });
  });
}
