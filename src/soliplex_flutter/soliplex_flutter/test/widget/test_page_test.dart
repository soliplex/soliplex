import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_flutter/features/test_page/test_page_feature.dart';

import '../mocks/mock_soliplex_client.dart';
import 'package:soliplex_flutter/providers/providers.dart';

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

    testWidgets('connect with empty URL logs error', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      // Clear the URL field
      final urlField = find.widgetWithText(TextField, 'Server URL');
      await tester.enterText(urlField, '');

      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Server URL is required'), findsOneWidget);
    });

    testWidgets('Get Threads without room ID logs error', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            soliplexClientProvider.overrideWithValue(mockClient),
          ],
          child: const MaterialApp(home: TestPage()),
        ),
      );

      // Connect first
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      // Tap Get Threads without entering room ID
      await tester.tap(find.text('Get Threads'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Room ID is required'), findsOneWidget);
    });

    testWidgets('Create Thread without room ID logs error', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            soliplexClientProvider.overrideWithValue(mockClient),
          ],
          child: const MaterialApp(home: TestPage()),
        ),
      );

      // Connect first
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      // Tap Create Thread without entering room ID
      await tester.tap(find.text('Create Thread'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Room ID is required'), findsOneWidget);
    });

    testWidgets('Delete Thread without IDs logs error', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            soliplexClientProvider.overrideWithValue(mockClient),
          ],
          child: const MaterialApp(home: TestPage()),
        ),
      );

      // Connect first
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      // Tap Delete Thread without entering IDs
      await tester.tap(find.text('Delete Thread'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Room ID and Thread ID are required'), findsOneWidget);
    });

    testWidgets('Create Run without IDs logs error', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            soliplexClientProvider.overrideWithValue(mockClient),
          ],
          child: const MaterialApp(home: TestPage()),
        ),
      );

      // Connect first
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      // Tap Create Run without entering IDs
      await tester.tap(find.text('Create Run'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Room ID and Thread ID are required'), findsOneWidget);
    });

    testWidgets('Set Meta without IDs logs error', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            soliplexClientProvider.overrideWithValue(mockClient),
          ],
          child: const MaterialApp(home: TestPage()),
        ),
      );

      // Connect first
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      // Tap Set Meta without entering IDs
      await tester.tap(find.text('Set Meta'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Room ID and Thread ID are required'), findsOneWidget);
    });

    testWidgets('Send message without Room ID logs error', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            soliplexClientProvider.overrideWithValue(mockClient),
          ],
          child: const MaterialApp(home: TestPage()),
        ),
      );

      // Connect first
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      // Enter message but no room ID
      await tester.enterText(find.widgetWithText(TextField, 'Message'), 'Test message');

      // Tap Send
      await tester.tap(find.text('Send'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Room ID and message are required'), findsOneWidget);
    });

    testWidgets('Send message without message text logs error', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            soliplexClientProvider.overrideWithValue(mockClient),
          ],
          child: const MaterialApp(home: TestPage()),
        ),
      );

      // Connect first
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      // Enter room ID but no message
      await tester.enterText(find.widgetWithText(TextField, 'Room ID'), 'room1');

      // Tap Send
      await tester.tap(find.text('Send'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Room ID and message are required'), findsOneWidget);
    });

    testWidgets('Get Rooms with mock client logs response', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            soliplexClientProvider.overrideWithValue(mockClient),
          ],
          child: const MaterialApp(home: TestPage()),
        ),
      );

      // Connect first
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      // Tap Get Rooms
      await tester.tap(find.text('Get Rooms'));
      // Wait for async operation to complete and UI to update
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.textContaining('GET /api/v1/rooms'), findsOneWidget);
      expect(find.textContaining('rooms'), findsWidgets);
    });

    testWidgets('Get Threads with room ID logs response', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            soliplexClientProvider.overrideWithValue(mockClient),
          ],
          child: const MaterialApp(home: TestPage()),
        ),
      );

      // Connect first
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      // Enter room ID
      await tester.enterText(find.widgetWithText(TextField, 'Room ID'), 'room1');

      // Tap Get Threads
      await tester.tap(find.text('Get Threads'));
      // Wait for async operation to complete and UI to update
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.textContaining('GET /api/v1/rooms/room1/agui'), findsOneWidget);
    });

    testWidgets('Create Thread with room ID logs response', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            soliplexClientProvider.overrideWithValue(mockClient),
          ],
          child: const MaterialApp(home: TestPage()),
        ),
      );

      // Connect first
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      // Enter room ID
      await tester.enterText(find.widgetWithText(TextField, 'Room ID'), 'room1');

      // Tap Create Thread
      await tester.tap(find.text('Create Thread'));
      // Wait for async operation to complete and UI to update
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Verify the request log appears
      expect(find.textContaining('POST /api/v1/rooms/room1/agui'), findsOneWidget);
    });

    testWidgets('Delete Thread with IDs logs response', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            soliplexClientProvider.overrideWithValue(mockClient),
          ],
          child: const MaterialApp(home: TestPage()),
        ),
      );

      // Connect first
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      // Enter room ID and thread ID
      await tester.enterText(find.widgetWithText(TextField, 'Room ID'), 'room1');
      await tester.enterText(find.widgetWithText(TextField, 'Thread ID'), 'thread1');

      // Tap Delete Thread
      await tester.tap(find.text('Delete Thread'));
      // Wait for async operation to complete and UI to update
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Verify the request log appears
      expect(find.textContaining('DELETE /api/v1/rooms/room1/agui/thread1'), findsOneWidget);
    });

    testWidgets('Create Run with IDs logs response', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            soliplexClientProvider.overrideWithValue(mockClient),
          ],
          child: const MaterialApp(home: TestPage()),
        ),
      );

      // Connect first
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      // Enter room ID and thread ID
      await tester.enterText(find.widgetWithText(TextField, 'Room ID'), 'room1');
      await tester.enterText(find.widgetWithText(TextField, 'Thread ID'), 'thread1');

      // Tap Create Run
      await tester.tap(find.text('Create Run'));
      // Wait for async operation to complete and UI to update
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Verify the request log appears
      expect(find.textContaining('POST /api/v1/rooms/room1/agui/thread1'), findsOneWidget);
    });

    testWidgets('Set Meta with IDs logs response', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            soliplexClientProvider.overrideWithValue(mockClient),
          ],
          child: const MaterialApp(home: TestPage()),
        ),
      );

      // Connect first
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      // Enter room ID and thread ID
      await tester.enterText(find.widgetWithText(TextField, 'Room ID'), 'room1');
      await tester.enterText(find.widgetWithText(TextField, 'Thread ID'), 'thread1');

      // Tap Set Meta
      await tester.tap(find.text('Set Meta'));
      // Wait for async operation to complete and UI to update
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Verify the request log appears
      expect(find.textContaining('POST /api/v1/rooms/room1/agui/thread1/meta'), findsOneWidget);
    });

    testWidgets('displays terminal icon in logs header', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      expect(find.byIcon(Icons.terminal), findsOneWidget);
    });

    testWidgets('displays app bar with title', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      expect(find.text('Test Page'), findsOneWidget);
      expect(find.byType(AppBar), findsOneWidget);
    });

    testWidgets('displays clear logs button in app bar', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      expect(find.byIcon(Icons.delete_sweep), findsOneWidget);
      expect(find.byTooltip('Clear logs'), findsOneWidget);
    });

    testWidgets('displays link icon before connect', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      expect(find.byIcon(Icons.link), findsOneWidget);
    });

    testWidgets('displays check circle icon after connect', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.check_circle), findsOneWidget);
    });

    testWidgets('displays correct endpoint button icons', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      expect(find.byIcon(Icons.meeting_room), findsOneWidget); // Get Rooms
      expect(find.byIcon(Icons.forum), findsOneWidget); // Get Threads
      expect(find.byIcon(Icons.add_comment), findsOneWidget); // Create Thread
      expect(find.byIcon(Icons.delete), findsOneWidget); // Delete Thread
      expect(find.byIcon(Icons.play_arrow), findsOneWidget); // Create Run
      expect(find.byIcon(Icons.edit), findsOneWidget); // Set Meta
    });

    testWidgets('displays send icon on send button', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      expect(find.byIcon(Icons.send), findsOneWidget);
    });

    testWidgets('message field shows hint text', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      expect(find.text('Enter chat message...'), findsOneWidget);
    });

    testWidgets('can enter text in message field', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      await tester.enterText(find.widgetWithText(TextField, 'Message'), 'Hello world');
      await tester.pump();

      expect(find.text('Hello world'), findsOneWidget);
    });

    testWidgets('can enter text in room ID field', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      await tester.enterText(find.widgetWithText(TextField, 'Room ID'), 'test-room');
      await tester.pump();

      expect(find.text('test-room'), findsOneWidget);
    });

    testWidgets('logs entry count updates', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(home: TestPage()),
        ),
      );

      expect(find.text('0 entries'), findsOneWidget);

      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      // Should have 2 entries: "Connecting..." and "Connected"
      expect(find.text('2 entries'), findsOneWidget);
    });
  });
}
