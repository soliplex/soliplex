import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/http_log_provider.dart';
import 'package:soliplex_frontend/features/inspector/http_inspector_panel.dart';
import 'package:soliplex_frontend/features/inspector/widgets/http_event_tile.dart';

import '../../helpers/test_helpers.dart';

void main() {
  group('HttpInspectorPanel', () {
    group('Empty state', () {
      testWidgets('shows empty message when no events', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: HttpInspectorPanel(),
            ),
          ),
        );

        expect(find.text('No HTTP activity yet'), findsOneWidget);
      });

      testWidgets('does not show event list when empty', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: HttpInspectorPanel(),
            ),
          ),
        );

        expect(find.byType(HttpEventTile), findsNothing);
      });
    });

    group('With events', () {
      testWidgets('displays grouped events in list', (tester) async {
        final events = [
          TestData.createRequestEvent(),
          TestData.createResponseEvent(),
          TestData.createRequestEvent(requestId: 'req-2'),
        ];

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              httpLogProvider.overrideWith(() => _MockHttpLogNotifier(events)),
            ],
            child: const MaterialApp(
              home: Scaffold(
                body: HttpInspectorPanel(),
              ),
            ),
          ),
        );

        // Two groups: req-1 (with response) and req-2 (pending)
        expect(find.byType(HttpEventTile), findsNWidgets(2));
      });

      testWidgets('hides empty message when events exist', (tester) async {
        final events = [TestData.createRequestEvent()];

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              httpLogProvider.overrideWith(() => _MockHttpLogNotifier(events)),
            ],
            child: const MaterialApp(
              home: Scaffold(
                body: HttpInspectorPanel(),
              ),
            ),
          ),
        );

        expect(find.text('No HTTP activity yet'), findsNothing);
      });

      testWidgets('events are scrollable', (tester) async {
        final events = List.generate(
          20,
          (i) => TestData.createRequestEvent(requestId: 'req-$i'),
        );

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              httpLogProvider.overrideWith(() => _MockHttpLogNotifier(events)),
            ],
            child: const MaterialApp(
              home: Scaffold(
                body: HttpInspectorPanel(),
              ),
            ),
          ),
        );

        expect(find.byType(ListView), findsOneWidget);
      });
    });

    group('Actions', () {
      testWidgets('has clear button', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: HttpInspectorPanel(),
            ),
          ),
        );

        expect(find.byIcon(Icons.delete_outline), findsOneWidget);
      });

      testWidgets('clear button calls notifier.clear()', (tester) async {
        final events = [TestData.createRequestEvent()];
        final notifier = _MockHttpLogNotifier(events);

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              httpLogProvider.overrideWith(() => notifier),
            ],
            child: const MaterialApp(
              home: Scaffold(
                body: HttpInspectorPanel(),
              ),
            ),
          ),
        );

        expect(notifier.clearWasCalled, isFalse);

        await tester.tap(find.byIcon(Icons.delete_outline));
        await tester.pump();

        expect(notifier.clearWasCalled, isTrue);
      });
    });

    group('Header', () {
      testWidgets('displays title', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const Scaffold(
              body: HttpInspectorPanel(),
            ),
          ),
        );

        expect(find.text('HTTP Inspector'), findsOneWidget);
      });

      testWidgets('displays request count', (tester) async {
        final events = [
          TestData.createRequestEvent(),
          TestData.createResponseEvent(),
          TestData.createRequestEvent(requestId: 'req-2'),
        ];

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              httpLogProvider.overrideWith(() => _MockHttpLogNotifier(events)),
            ],
            child: const MaterialApp(
              home: Scaffold(
                body: HttpInspectorPanel(),
              ),
            ),
          ),
        );

        // Shows group count (2 requests: req-1 and req-2)
        expect(find.text('2 requests'), findsOneWidget);
      });

      testWidgets('uses singular for single request', (tester) async {
        final events = [TestData.createRequestEvent()];

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              httpLogProvider.overrideWith(() => _MockHttpLogNotifier(events)),
            ],
            child: const MaterialApp(
              home: Scaffold(
                body: HttpInspectorPanel(),
              ),
            ),
          ),
        );

        expect(find.text('1 request'), findsOneWidget);
      });
    });
  });
}

class _MockHttpLogNotifier extends HttpLogNotifier {
  _MockHttpLogNotifier(this._initialEvents);

  final List<HttpEvent> _initialEvents;
  bool clearWasCalled = false;

  @override
  List<HttpEvent> build() => _initialEvents;

  @override
  void clear() {
    clearWasCalled = true;
    state = [];
  }
}
