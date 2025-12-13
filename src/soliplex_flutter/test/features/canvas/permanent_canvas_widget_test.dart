import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_flutter/features/canvas/permanent_canvas_widget.dart';

void main() {
  Widget wrapWidget(Widget widget, {List<Override> overrides = const []}) {
    return ProviderScope(
      overrides: overrides,
      child: MaterialApp(
        home: Scaffold(body: widget),
      ),
    );
  }

  group('PinnedItem', () {
    test('creates with required fields', () {
      final item = PinnedItem(
        id: 'test-id',
        title: 'Test Title',
        content: 'Test Content',
        pinnedAt: DateTime(2024, 1, 15, 10, 30),
      );

      expect(item.id, 'test-id');
      expect(item.title, 'Test Title');
      expect(item.content, 'Test Content');
      expect(item.pinnedAt, DateTime(2024, 1, 15, 10, 30));
      expect(item.type, 'text');
      expect(item.roomId, isNull);
      expect(item.threadId, isNull);
    });

    test('creates with all fields', () {
      final item = PinnedItem(
        id: 'test-id',
        title: 'Test Title',
        content: 'Test Content',
        pinnedAt: DateTime(2024, 1, 15),
        roomId: 'room-1',
        threadId: 'thread-1',
        type: 'code',
      );

      expect(item.roomId, 'room-1');
      expect(item.threadId, 'thread-1');
      expect(item.type, 'code');
    });

    test('fromJson parses correctly', () {
      final json = {
        'id': 'json-id',
        'title': 'JSON Title',
        'content': 'JSON Content',
        'pinnedAt': '2024-01-15T10:30:00.000',
        'roomId': 'room-1',
        'threadId': 'thread-1',
        'type': 'code',
      };

      final item = PinnedItem.fromJson(json);

      expect(item.id, 'json-id');
      expect(item.title, 'JSON Title');
      expect(item.content, 'JSON Content');
      expect(item.roomId, 'room-1');
      expect(item.threadId, 'thread-1');
      expect(item.type, 'code');
    });

    test('fromJson uses default type when missing', () {
      final json = {
        'id': 'json-id',
        'title': 'JSON Title',
        'content': 'JSON Content',
        'pinnedAt': '2024-01-15T10:30:00.000',
      };

      final item = PinnedItem.fromJson(json);

      expect(item.type, 'text');
    });

    test('toJson serializes correctly', () {
      final item = PinnedItem(
        id: 'test-id',
        title: 'Test Title',
        content: 'Test Content',
        pinnedAt: DateTime(2024, 1, 15, 10, 30),
        roomId: 'room-1',
        threadId: 'thread-1',
        type: 'code',
      );

      final json = item.toJson();

      expect(json['id'], 'test-id');
      expect(json['title'], 'Test Title');
      expect(json['content'], 'Test Content');
      expect(json['roomId'], 'room-1');
      expect(json['threadId'], 'thread-1');
      expect(json['type'], 'code');
      expect(json['pinnedAt'], contains('2024-01-15'));
    });

    test('copyWith creates modified copy', () {
      final original = PinnedItem(
        id: 'original-id',
        title: 'Original Title',
        content: 'Original Content',
        pinnedAt: DateTime(2024, 1, 15),
      );

      final copied = original.copyWith(title: 'New Title');

      expect(copied.id, 'original-id');
      expect(copied.title, 'New Title');
      expect(copied.content, 'Original Content');
    });

    test('copyWith preserves all fields when not specified', () {
      final original = PinnedItem(
        id: 'original-id',
        title: 'Original Title',
        content: 'Original Content',
        pinnedAt: DateTime(2024, 1, 15),
        roomId: 'room-1',
        threadId: 'thread-1',
        type: 'code',
      );

      final copied = original.copyWith();

      expect(copied.id, original.id);
      expect(copied.title, original.title);
      expect(copied.content, original.content);
      expect(copied.roomId, original.roomId);
      expect(copied.threadId, original.threadId);
      expect(copied.type, original.type);
    });
  });

  group('PinnedItemsNotifier', () {
    test('starts with empty list when prefs is null', () {
      final notifier = PinnedItemsNotifier(null);

      expect(notifier.state, isEmpty);
    });

    test('addItem adds to state', () {
      final notifier = PinnedItemsNotifier(null);
      final item = PinnedItem(
        id: 'item-1',
        title: 'Item 1',
        content: 'Content 1',
        pinnedAt: DateTime.now(),
      );

      notifier.addItem(item);

      expect(notifier.state.length, 1);
      expect(notifier.state.first.id, 'item-1');
    });

    test('removeItem removes from state', () {
      final notifier = PinnedItemsNotifier(null);
      final item = PinnedItem(
        id: 'item-1',
        title: 'Item 1',
        content: 'Content 1',
        pinnedAt: DateTime.now(),
      );

      notifier.addItem(item);
      expect(notifier.state.length, 1);

      notifier.removeItem('item-1');
      expect(notifier.state, isEmpty);
    });

    test('updateItem updates existing item', () {
      final notifier = PinnedItemsNotifier(null);
      final item = PinnedItem(
        id: 'item-1',
        title: 'Original Title',
        content: 'Content 1',
        pinnedAt: DateTime.now(),
      );

      notifier.addItem(item);

      final updatedItem = item.copyWith(title: 'Updated Title');
      notifier.updateItem('item-1', updatedItem);

      expect(notifier.state.first.title, 'Updated Title');
    });

    test('reorder moves item from lower to higher index', () {
      final notifier = PinnedItemsNotifier(null);
      notifier.addItem(PinnedItem(
        id: 'item-1',
        title: 'Item 1',
        content: '',
        pinnedAt: DateTime.now(),
      ));
      notifier.addItem(PinnedItem(
        id: 'item-2',
        title: 'Item 2',
        content: '',
        pinnedAt: DateTime.now(),
      ));
      notifier.addItem(PinnedItem(
        id: 'item-3',
        title: 'Item 3',
        content: '',
        pinnedAt: DateTime.now(),
      ));

      // Move item-1 to position 2
      notifier.reorder(0, 2);

      expect(notifier.state[0].id, 'item-2');
      expect(notifier.state[1].id, 'item-1');
      expect(notifier.state[2].id, 'item-3');
    });

    test('reorder moves item from higher to lower index', () {
      final notifier = PinnedItemsNotifier(null);
      notifier.addItem(PinnedItem(
        id: 'item-1',
        title: 'Item 1',
        content: '',
        pinnedAt: DateTime.now(),
      ));
      notifier.addItem(PinnedItem(
        id: 'item-2',
        title: 'Item 2',
        content: '',
        pinnedAt: DateTime.now(),
      ));
      notifier.addItem(PinnedItem(
        id: 'item-3',
        title: 'Item 3',
        content: '',
        pinnedAt: DateTime.now(),
      ));

      // Move item-3 to position 0
      notifier.reorder(2, 0);

      expect(notifier.state[0].id, 'item-3');
      expect(notifier.state[1].id, 'item-1');
      expect(notifier.state[2].id, 'item-2');
    });
  });

  group('PermanentCanvasWidget', () {
    testWidgets('displays empty state when no items', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => PinnedItemsNotifier(null)),
        ],
      ));

      await tester.pump();

      expect(find.text('No pinned items'), findsOneWidget);
      expect(find.text('Pin items to keep them across sessions'), findsOneWidget);
      expect(find.byIcon(Icons.push_pin_outlined), findsOneWidget);
    });

    testWidgets('displays header with item count', (tester) async {
      final notifier = PinnedItemsNotifier(null)
        ..addItem(PinnedItem(
          id: 'item-1',
          title: 'Item 1',
          content: 'Content 1',
          pinnedAt: DateTime.now(),
        ));

      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => notifier),
        ],
      ));

      await tester.pump();
      await tester.pump();

      expect(find.text('Pinned (1)'), findsOneWidget);
      expect(find.byIcon(Icons.push_pin), findsWidgets);
    });

    testWidgets('displays add button', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => PinnedItemsNotifier(null)),
        ],
      ));

      await tester.pump();

      expect(find.byIcon(Icons.add), findsOneWidget);
      expect(find.byTooltip('Add Item'), findsOneWidget);
    });

    testWidgets('opens add dialog when add button tapped', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => PinnedItemsNotifier(null)),
        ],
      ));

      await tester.pump();

      await tester.tap(find.byIcon(Icons.add));
      await tester.pumpAndSettle();

      expect(find.text('Add Pinned Item'), findsOneWidget);
      expect(find.text('Title'), findsOneWidget);
      expect(find.text('Content'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
      expect(find.text('Add'), findsOneWidget);
    });

    testWidgets('cancels add dialog without adding', (tester) async {
      final notifier = PinnedItemsNotifier(null);

      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => notifier),
        ],
      ));

      await tester.pump();

      await tester.tap(find.byIcon(Icons.add));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(notifier.state, isEmpty);
    });

    testWidgets('adds item when add dialog submitted', (tester) async {
      final notifier = PinnedItemsNotifier(null);

      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => notifier),
        ],
      ));

      await tester.pump();

      await tester.tap(find.byIcon(Icons.add));
      await tester.pumpAndSettle();

      // Enter title
      await tester.enterText(find.widgetWithText(TextField, 'Title'), 'New Item');
      await tester.enterText(find.widgetWithText(TextField, 'Content'), 'Item content');

      await tester.tap(find.text('Add'));
      await tester.pump();
      await tester.pump();

      expect(notifier.state.length, 1);
      expect(notifier.state.first.title, 'New Item');
    });

    testWidgets('does not add item with empty title', (tester) async {
      final notifier = PinnedItemsNotifier(null);

      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => notifier),
        ],
      ));

      await tester.pump();

      await tester.tap(find.byIcon(Icons.add));
      await tester.pumpAndSettle();

      // Leave title empty, just add content
      await tester.enterText(find.widgetWithText(TextField, 'Content'), 'Content only');

      await tester.tap(find.text('Add'));
      await tester.pump();
      await tester.pump();

      expect(notifier.state, isEmpty);
    });
  });

  group('_PinnedItemsList', () {
    testWidgets('displays pinned items', (tester) async {
      final notifier = PinnedItemsNotifier(null)
        ..addItem(PinnedItem(
          id: 'item-1',
          title: 'First Item',
          content: 'First content',
          pinnedAt: DateTime.now(),
        ))
        ..addItem(PinnedItem(
          id: 'item-2',
          title: 'Second Item',
          content: 'Second content',
          pinnedAt: DateTime.now(),
        ));

      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => notifier),
        ],
      ));

      await tester.pump();
      await tester.pump();

      expect(find.text('First Item'), findsOneWidget);
      expect(find.text('Second Item'), findsOneWidget);
    });

    testWidgets('displays delete button for each item', (tester) async {
      final notifier = PinnedItemsNotifier(null)
        ..addItem(PinnedItem(
          id: 'item-1',
          title: 'Item 1',
          content: 'Content',
          pinnedAt: DateTime.now(),
        ));

      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => notifier),
        ],
      ));

      await tester.pump();
      await tester.pump();

      expect(find.byIcon(Icons.delete_outline), findsOneWidget);
    });

    testWidgets('deletes item when delete button tapped', (tester) async {
      final notifier = PinnedItemsNotifier(null)
        ..addItem(PinnedItem(
          id: 'item-1',
          title: 'Item to Delete',
          content: 'Content',
          pinnedAt: DateTime.now(),
        ));

      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => notifier),
        ],
      ));

      await tester.pump();
      await tester.pump();

      expect(notifier.state.length, 1);

      await tester.tap(find.byIcon(Icons.delete_outline));
      await tester.pump();

      expect(notifier.state, isEmpty);
    });
  });

  group('_PinnedItemCard', () {
    testWidgets('displays title and content', (tester) async {
      final notifier = PinnedItemsNotifier(null)
        ..addItem(PinnedItem(
          id: 'item-1',
          title: 'Card Title',
          content: 'Card Content',
          pinnedAt: DateTime.now(),
        ));

      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => notifier),
        ],
      ));

      await tester.pump();
      await tester.pump();

      expect(find.text('Card Title'), findsOneWidget);
      expect(find.text('Card Content'), findsOneWidget);
    });

    testWidgets('displays time icon', (tester) async {
      final notifier = PinnedItemsNotifier(null)
        ..addItem(PinnedItem(
          id: 'item-1',
          title: 'Item',
          content: '',
          pinnedAt: DateTime.now(),
        ));

      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => notifier),
        ],
      ));

      await tester.pump();
      await tester.pump();

      expect(find.byIcon(Icons.access_time), findsOneWidget);
    });

    testWidgets('shows Today for items pinned today', (tester) async {
      final notifier = PinnedItemsNotifier(null)
        ..addItem(PinnedItem(
          id: 'item-1',
          title: 'Today Item',
          content: '',
          pinnedAt: DateTime.now(),
        ));

      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => notifier),
        ],
      ));

      await tester.pump();
      await tester.pump();

      expect(find.textContaining('Today at'), findsOneWidget);
    });

    testWidgets('shows Yesterday for items pinned yesterday', (tester) async {
      final yesterday = DateTime.now().subtract(const Duration(days: 1));
      final notifier = PinnedItemsNotifier(null)
        ..addItem(PinnedItem(
          id: 'item-1',
          title: 'Yesterday Item',
          content: '',
          pinnedAt: yesterday,
        ));

      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => notifier),
        ],
      ));

      await tester.pump();
      await tester.pump();

      expect(find.text('Yesterday'), findsOneWidget);
    });

    testWidgets('shows days ago for items within week', (tester) async {
      final threeDaysAgo = DateTime.now().subtract(const Duration(days: 3));
      final notifier = PinnedItemsNotifier(null)
        ..addItem(PinnedItem(
          id: 'item-1',
          title: 'Old Item',
          content: '',
          pinnedAt: threeDaysAgo,
        ));

      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => notifier),
        ],
      ));

      await tester.pump();
      await tester.pump();

      expect(find.text('3 days ago'), findsOneWidget);
    });

    testWidgets('shows date for items older than week', (tester) async {
      final twoWeeksAgo = DateTime.now().subtract(const Duration(days: 14));
      final notifier = PinnedItemsNotifier(null)
        ..addItem(PinnedItem(
          id: 'item-1',
          title: 'Very Old Item',
          content: '',
          pinnedAt: twoWeeksAgo,
        ));

      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => notifier),
        ],
      ));

      await tester.pump();
      await tester.pump();

      // Check for date format month/day/year
      expect(find.textContaining('/'), findsOneWidget);
    });

    testWidgets('hides content when empty', (tester) async {
      final notifier = PinnedItemsNotifier(null)
        ..addItem(PinnedItem(
          id: 'item-1',
          title: 'Title Only',
          content: '',
          pinnedAt: DateTime.now(),
        ));

      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => notifier),
        ],
      ));

      await tester.pump();
      await tester.pump();

      expect(find.text('Title Only'), findsOneWidget);
      // SelectableText for content should not exist or be empty
      expect(find.byType(SelectableText), findsNothing);
    });
  });

  group('_EmptyPermanentCanvas', () {
    testWidgets('displays empty state message', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const PermanentCanvasWidget(),
        overrides: [
          pinnedItemsProvider.overrideWith((ref) => PinnedItemsNotifier(null)),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.push_pin_outlined), findsOneWidget);
      expect(find.text('No pinned items'), findsOneWidget);
      expect(find.text('Pin items to keep them across sessions'), findsOneWidget);
    });
  });
}
