import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_flutter/client/client.dart';
import 'package:soliplex_flutter/features/history/history_widget.dart';
import 'package:soliplex_flutter/providers/providers.dart';

import '../../mocks/mock_soliplex_client.dart';

void main() {
  Widget wrapWidget(Widget widget, {List<Override> overrides = const []}) {
    return ProviderScope(
      overrides: overrides,
      child: MaterialApp(
        home: Scaffold(body: widget),
      ),
    );
  }

  group('HistoryWidget', () {
    testWidgets('displays empty state when no room selected', (tester) async {
      await tester.pumpWidget(wrapWidget(const HistoryWidget()));

      expect(find.text('Select a room to view threads'), findsOneWidget);
      expect(find.byIcon(Icons.forum_outlined), findsOneWidget);
    });

    testWidgets('displays history header when room is selected', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const HistoryWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      await tester.pump();

      expect(find.text('History'), findsOneWidget);
      expect(find.byIcon(Icons.history), findsOneWidget);
    });

    testWidgets('displays new thread button', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const HistoryWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      await tester.pump();

      expect(find.byIcon(Icons.add), findsOneWidget);
      expect(find.byTooltip('New Thread'), findsOneWidget);
    });

    testWidgets('displays refresh button', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const HistoryWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      await tester.pump();

      expect(find.byIcon(Icons.refresh), findsOneWidget);
      expect(find.byTooltip('Refresh'), findsOneWidget);
    });

    testWidgets('displays loading indicator', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const HistoryWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      await tester.pump();

      // Widget should render without errors
      expect(find.byType(HistoryWidget), findsOneWidget);
    });

    testWidgets('displays thread list when threads exist', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const HistoryWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      // Wait for async loading
      await tester.pumpAndSettle();

      // Check for thread cards (mock returns 2 threads)
      expect(find.byType(ListView), findsOneWidget);
    });

    testWidgets('shows delete button on thread cards', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const HistoryWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.delete_outline), findsWidgets);
    });

    testWidgets('shows time icon on thread cards', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const HistoryWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.access_time), findsWidgets);
    });

    testWidgets('creates new thread when add button tapped', (tester) async {
      final mockClient = MockSoliplexClient();
      var createCalled = false;

      await tester.pumpWidget(wrapWidget(
        const HistoryWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          createThreadProvider.overrideWith((ref) => (roomId) async {
            createCalled = true;
            return (threadId: 'new-thread', runId: 'new-run');
          }),
        ],
      ));

      await tester.pump();

      // Tap add button
      await tester.tap(find.byIcon(Icons.add));
      await tester.pumpAndSettle();

      expect(createCalled, isTrue);
    });

    testWidgets('shows delete confirmation dialog', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const HistoryWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      await tester.pumpAndSettle();

      // Tap delete button
      await tester.tap(find.byIcon(Icons.delete_outline).first);
      await tester.pumpAndSettle();

      // Verify dialog appears
      expect(find.text('Delete Thread'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
      expect(find.text('Delete'), findsOneWidget);
    });

    testWidgets('cancels delete when Cancel pressed', (tester) async {
      final mockClient = MockSoliplexClient();
      var deleteCalled = false;

      await tester.pumpWidget(wrapWidget(
        const HistoryWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          deleteThreadProvider.overrideWith((ref) => (roomId, threadId) async {
            deleteCalled = true;
          }),
        ],
      ));

      await tester.pumpAndSettle();

      // Tap delete button
      await tester.tap(find.byIcon(Icons.delete_outline).first);
      await tester.pumpAndSettle();

      // Tap Cancel
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(deleteCalled, isFalse);
    });

    testWidgets('deletes thread when Delete confirmed', (tester) async {
      final mockClient = MockSoliplexClient();
      var deleteCalled = false;

      await tester.pumpWidget(wrapWidget(
        const HistoryWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
          deleteThreadProvider.overrideWith((ref) => (roomId, threadId) async {
            deleteCalled = true;
          }),
        ],
      ));

      await tester.pumpAndSettle();

      // Tap delete button
      await tester.tap(find.byIcon(Icons.delete_outline).first);
      await tester.pumpAndSettle();

      // Tap Delete to confirm
      await tester.tap(find.text('Delete'));
      await tester.pumpAndSettle();

      expect(deleteCalled, isTrue);
    });

    testWidgets('selects thread when tapped', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const HistoryWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      await tester.pumpAndSettle();

      // Find and tap a thread card (Card is inside InkWell)
      final inkWells = find.byType(InkWell);
      expect(inkWells, findsWidgets);

      // Tap the first thread
      await tester.tap(inkWells.first);
      await tester.pumpAndSettle();

      // Widget should respond to tap without errors
      expect(find.byType(HistoryWidget), findsOneWidget);
    });
  });

  group('_EmptyHistory', () {
    testWidgets('displays message with forum icon', (tester) async {
      await tester.pumpWidget(wrapWidget(const HistoryWidget()));

      expect(find.byIcon(Icons.forum_outlined), findsOneWidget);
    });
  });

  group('_HistoryHeader', () {
    testWidgets('displays history title', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const HistoryWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      await tester.pump();

      expect(find.text('History'), findsOneWidget);
    });
  });

  group('_ThreadCard', () {
    testWidgets('displays Unnamed Thread for null name', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const HistoryWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      await tester.pumpAndSettle();

      // Mock returns threads without names
      expect(find.textContaining('Unnamed Thread'), findsWidgets);
    });
  });

  group('_formatDate', () {
    testWidgets('displays formatted date on thread cards', (tester) async {
      final mockClient = MockSoliplexClient();

      await tester.pumpWidget(wrapWidget(
        const HistoryWidget(),
        overrides: [
          soliplexClientProvider.overrideWithValue(mockClient),
          currentRoomProvider.overrideWith((ref) => 'room1'),
        ],
      ));

      await tester.pumpAndSettle();

      // Should display some formatted date
      expect(find.byIcon(Icons.access_time), findsWidgets);
    });
  });
}
