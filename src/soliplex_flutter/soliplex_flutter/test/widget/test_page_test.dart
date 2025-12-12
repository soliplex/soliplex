import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_flutter/features/test_page/test_page_feature.dart';

void main() {
  group('TestPage', () {
    testWidgets('displays server URL input', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      expect(find.text('Server URL'), findsOneWidget);
      expect(find.text('http://localhost:8000'), findsOneWidget);
    });

    testWidgets('displays connect button', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      expect(find.text('Connect'), findsOneWidget);
    });

    testWidgets('displays endpoint buttons', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      expect(find.text('Get Rooms'), findsOneWidget);
      expect(find.text('Get Threads'), findsOneWidget);
      expect(find.text('Create Thread'), findsOneWidget);
      expect(find.text('Delete Thread'), findsOneWidget);
      expect(find.text('Create Run'), findsOneWidget);
      expect(find.text('Set Meta'), findsOneWidget);
    });

    testWidgets('displays ID input fields', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      expect(find.text('Room ID'), findsOneWidget);
      expect(find.text('Thread ID'), findsOneWidget);
      expect(find.text('Run ID'), findsOneWidget);
    });

    testWidgets('displays message input and send button', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      expect(find.text('Message'), findsOneWidget);
      expect(find.text('Send'), findsOneWidget);
    });

    testWidgets('displays logs section', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      expect(find.text('Logs'), findsOneWidget);
      expect(find.text('0 entries'), findsOneWidget);
    });

    testWidgets('connect button changes state on tap', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      expect(find.text('Connect'), findsOneWidget);

      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      expect(find.text('Connected'), findsOneWidget);
    });

    testWidgets('endpoint buttons are disabled before connect', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      final getRoomsButton = tester.widget<ElevatedButton>(
        find.ancestor(
          of: find.text('Get Rooms'),
          matching: find.byType(ElevatedButton),
        ),
      );

      expect(getRoomsButton.onPressed, isNull);
    });

    testWidgets('endpoint buttons are enabled after connect', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      final getRoomsButton = tester.widget<ElevatedButton>(
        find.ancestor(
          of: find.text('Get Rooms'),
          matching: find.byType(ElevatedButton),
        ),
      );

      expect(getRoomsButton.onPressed, isNotNull);
    });

    testWidgets('clear logs button clears log entries', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      // Connect to generate a log entry
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      // Verify log entries exist
      expect(find.text('0 entries'), findsNothing);

      // Clear logs
      await tester.tap(find.byIcon(Icons.delete_sweep));
      await tester.pumpAndSettle();

      expect(find.text('0 entries'), findsOneWidget);
    });
  });
}
