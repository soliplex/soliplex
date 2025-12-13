import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_flutter/features/canvas/current_canvas_widget.dart';
import 'package:soliplex_flutter/providers/providers.dart';

void main() {
  Widget wrapWidget(Widget widget, {List<Override> overrides = const []}) {
    return ProviderScope(
      overrides: overrides,
      child: MaterialApp(
        home: Scaffold(body: widget),
      ),
    );
  }

  group('CurrentCanvasWidget', () {
    testWidgets('displays empty state when canvas is empty', (tester) async {
      await tester.pumpWidget(wrapWidget(const CurrentCanvasWidget()));

      expect(find.text('No canvas data yet'), findsOneWidget);
      expect(find.byIcon(Icons.dashboard_outlined), findsOneWidget);
    });

    testWidgets('displays waiting state when agent is active', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          isAgentActiveProvider.overrideWith((ref) => true),
        ],
      ));

      await tester.pump();

      expect(find.text('Waiting for canvas data...'), findsOneWidget);
      expect(find.byIcon(Icons.hourglass_top), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('displays canvas header when data exists', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'testKey': 'testValue',
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('Canvas'), findsOneWidget);
      expect(find.byIcon(Icons.dashboard), findsOneWidget);
    });

    testWidgets('displays clear button', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'key': 'value',
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.clear_all), findsOneWidget);
      expect(find.byTooltip('Clear Canvas'), findsOneWidget);
    });

    testWidgets('clears canvas when clear button is tapped', (tester) async {
      final notifier = CanvasStateNotifier()..updateState({'key': 'value'});

      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => notifier),
        ],
      ));

      await tester.pumpAndSettle();

      // Verify data is shown
      expect(find.text('key'), findsOneWidget);

      // Tap clear button
      await tester.tap(find.byIcon(Icons.clear_all));
      await tester.pumpAndSettle();

      // Canvas should now be empty
      expect(find.text('No canvas data yet'), findsOneWidget);
    });
  });

  group('_EmptyCanvas', () {
    testWidgets('displays inactive state correctly', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          isAgentActiveProvider.overrideWith((ref) => false),
        ],
      ));

      await tester.pump();

      expect(find.byIcon(Icons.dashboard_outlined), findsOneWidget);
      expect(find.text('No canvas data yet'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });

    testWidgets('displays active state with loading indicator', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          isAgentActiveProvider.overrideWith((ref) => true),
        ],
      ));

      await tester.pump();

      expect(find.byIcon(Icons.hourglass_top), findsOneWidget);
      expect(find.text('Waiting for canvas data...'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });
  });

  group('_StateCard', () {
    testWidgets('displays string value with text icon', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'stringKey': 'hello world',
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('stringKey'), findsOneWidget);
      expect(find.text('string'), findsOneWidget);
      expect(find.byIcon(Icons.text_fields), findsOneWidget);
    });

    testWidgets('displays integer value with number icon', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'intKey': 42,
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('intKey'), findsOneWidget);
      expect(find.text('int'), findsOneWidget);
      expect(find.byIcon(Icons.numbers), findsOneWidget);
    });

    testWidgets('displays double value with number icon', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'doubleKey': 3.14,
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('doubleKey'), findsOneWidget);
      expect(find.text('double'), findsOneWidget);
      expect(find.byIcon(Icons.numbers), findsOneWidget);
    });

    testWidgets('displays boolean value with toggle icon', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'boolKey': true,
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('boolKey'), findsOneWidget);
      expect(find.text('bool'), findsOneWidget);
      expect(find.byIcon(Icons.toggle_on), findsOneWidget);
    });

    testWidgets('displays map value with object icon', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'mapKey': {'nested': 'value'},
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('mapKey'), findsOneWidget);
      expect(find.text('object'), findsOneWidget);
      expect(find.byIcon(Icons.data_object), findsOneWidget);
    });

    testWidgets('displays list value with array icon', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'listKey': [1, 2, 3],
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('listKey'), findsOneWidget);
      expect(find.text('array[3]'), findsOneWidget);
      expect(find.byIcon(Icons.data_array), findsOneWidget);
    });
  });

  group('_MapDisplay', () {
    testWidgets('displays map entries', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'mapKey': {'first': 'value1', 'second': 'value2'},
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.textContaining('first:'), findsOneWidget);
      expect(find.textContaining('second:'), findsOneWidget);
    });

    testWidgets('truncates long string values', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'mapKey': {'longKey': 'a' * 60}, // String > 50 chars
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.textContaining('...'), findsWidgets);
    });

    testWidgets('displays nested map as {...}', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'mapKey': {'nested': {'deep': 'value'}},
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.textContaining('{...}'), findsOneWidget);
    });

    testWidgets('displays nested list as [N items]', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'mapKey': {'list': [1, 2, 3]},
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.textContaining('[3 items]'), findsOneWidget);
    });
  });

  group('_ListDisplay', () {
    testWidgets('displays list items with indices', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'listKey': ['one', 'two', 'three'],
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('[0] '), findsOneWidget);
      expect(find.text('[1] '), findsOneWidget);
      expect(find.text('[2] '), findsOneWidget);
    });

    testWidgets('shows more items message when list > 5 items', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'listKey': [1, 2, 3, 4, 5, 6, 7, 8],
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.textContaining('... and 3 more items'), findsOneWidget);
    });

    testWidgets('truncates long string items', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'listKey': ['a' * 40], // String > 30 chars
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.textContaining('...'), findsWidgets);
    });

    testWidgets('displays nested maps as {...}', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'listKey': [{'nested': 'map'}],
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.textContaining('{...}'), findsOneWidget);
    });

    testWidgets('displays nested lists as [N]', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'listKey': [[1, 2, 3]],
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.textContaining('[3]'), findsOneWidget);
    });
  });

  group('_ValueDisplay', () {
    testWidgets('displays primitive values in container', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'strKey': 'simple string',
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('simple string'), findsOneWidget);
    });
  });

  group('_CanvasContent', () {
    testWidgets('displays multiple state cards', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'key1': 'value1',
            'key2': 42,
            'key3': true,
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.text('key1'), findsOneWidget);
      expect(find.text('key2'), findsOneWidget);
      expect(find.text('key3'), findsOneWidget);
    });

    testWidgets('uses ListView for scrollable content', (tester) async {
      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => CanvasStateNotifier()..updateState({
            'key': 'value',
          })),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.byType(ListView), findsOneWidget);
    });
  });

  group('Unknown type handling', () {
    testWidgets('displays help icon for unknown types', (tester) async {
      // Create a custom notifier that can hold any type
      final notifier = CanvasStateNotifier();
      // Manually set a value that's not a standard type
      notifier.updateState({'unknownType': Object()});

      await tester.pumpWidget(wrapWidget(
        const CurrentCanvasWidget(),
        overrides: [
          canvasStateProvider.overrideWith((ref) => notifier),
        ],
      ));

      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.help_outline), findsOneWidget);
    });
  });
}
