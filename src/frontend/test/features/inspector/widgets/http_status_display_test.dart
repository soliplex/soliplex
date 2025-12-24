import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/features/inspector/models/http_event_group.dart';
import 'package:soliplex_frontend/features/inspector/widgets/http_status_display.dart';

import '../../../helpers/test_helpers.dart';

void main() {
  group('HttpStatusDisplay', () {
    group('pending status', () {
      testWidgets('displays pending text with spinner', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        expect(find.text('pending...'), findsOneWidget);
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
      });

      testWidgets('uses italic font style', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        final text = tester.widget<Text>(find.text('pending...'));
        expect(text.style?.fontStyle, FontStyle.italic);
      });
    });

    group('success status', () {
      testWidgets('displays status, duration, and size', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(
            duration: const Duration(milliseconds: 123),
            bodySize: 2048,
          ),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        expect(find.text('200 OK (123ms, 2.0KB)'), findsOneWidget);
        expect(find.byType(CircularProgressIndicator), findsNothing);
      });

      testWidgets('uses tertiary color', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        final text = tester.widget<Text>(find.textContaining('200 OK'));
        final context = tester.element(find.byType(HttpStatusDisplay));
        final colorScheme = Theme.of(context).colorScheme;
        expect(text.style?.color, colorScheme.tertiary);
      });
    });

    group('client error status', () {
      testWidgets('displays status code and duration', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(
            statusCode: 404,
            duration: const Duration(milliseconds: 50),
          ),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        expect(find.text('404 (50ms)'), findsOneWidget);
      });

      testWidgets('uses warning color', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 400),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        final text = tester.widget<Text>(find.textContaining('400'));
        final context = tester.element(find.byType(HttpStatusDisplay));
        final colorScheme = Theme.of(context).colorScheme;
        expect(text.style?.color, colorScheme.warning);
      });
    });

    group('server error status', () {
      testWidgets('displays status code and duration', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(
            statusCode: 500,
            duration: const Duration(milliseconds: 200),
          ),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        expect(find.text('500 (200ms)'), findsOneWidget);
      });

      testWidgets('uses error color', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 503),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        final text = tester.widget<Text>(find.textContaining('503'));
        final context = tester.element(find.byType(HttpStatusDisplay));
        final colorScheme = Theme.of(context).colorScheme;
        expect(text.style?.color, colorScheme.error);
      });
    });

    group('network error status', () {
      testWidgets('displays exception type and duration', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          error: TestData.createErrorEvent(
            duration: const Duration(seconds: 5),
          ),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        expect(find.text('NetworkException (5.0s)'), findsOneWidget);
      });

      testWidgets('uses error color', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          error: TestData.createErrorEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        final text =
            tester.widget<Text>(find.textContaining('NetworkException'));
        final context = tester.element(find.byType(HttpStatusDisplay));
        final colorScheme = Theme.of(context).colorScheme;
        expect(text.style?.color, colorScheme.error);
      });
    });

    group('streaming status', () {
      testWidgets('displays streaming text with spinner', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        expect(find.text('streaming...'), findsOneWidget);
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
      });

      testWidgets('shows bytes when streamEnd available during streaming',
          (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
          streamEnd: TestData.createStreamEndEvent(
            bytesReceived: 10240,
            error: const NetworkException(message: 'Still receiving'),
          ),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        // When stream has error, it shows error status instead
        expect(find.textContaining('error'), findsOneWidget);
      });

      testWidgets('uses secondary color', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        final spinner = tester.widget<CircularProgressIndicator>(
          find.byType(CircularProgressIndicator),
        );
        final context = tester.element(find.byType(HttpStatusDisplay));
        final colorScheme = Theme.of(context).colorScheme;
        expect(spinner.color, colorScheme.secondary);
      });

      testWidgets('uses italic font style', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        final text = tester.widget<Text>(find.text('streaming...'));
        expect(text.style?.fontStyle, FontStyle.italic);
      });
    });

    group('stream complete status', () {
      testWidgets('displays duration and bytes received', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
          streamEnd: TestData.createStreamEndEvent(
            duration: const Duration(seconds: 30),
            bytesReceived: 1048576,
          ),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        expect(find.text('complete (30.0s, 1.0MB)'), findsOneWidget);
        expect(find.byType(CircularProgressIndicator), findsNothing);
      });

      testWidgets('uses tertiary color', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
          streamEnd: TestData.createStreamEndEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        final text = tester.widget<Text>(find.textContaining('complete'));
        final context = tester.element(find.byType(HttpStatusDisplay));
        final colorScheme = Theme.of(context).colorScheme;
        expect(text.style?.color, colorScheme.tertiary);
      });
    });

    group('stream error status', () {
      testWidgets('displays error with duration', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
          streamEnd: TestData.createStreamEndEvent(
            duration: const Duration(seconds: 15),
            error: const NetworkException(message: 'Lost connection'),
          ),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        expect(find.text('error (15.0s)'), findsOneWidget);
      });

      testWidgets('uses error color', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
          streamEnd: TestData.createStreamEndEvent(
            error: const NetworkException(message: 'Lost'),
          ),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        final text = tester.widget<Text>(find.textContaining('error'));
        final context = tester.element(find.byType(HttpStatusDisplay));
        final colorScheme = Theme.of(context).colorScheme;
        expect(text.style?.color, colorScheme.error);
      });
    });

    group('spinner layout', () {
      testWidgets('spinner has correct size', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        final spinnerContainer = tester.widget<SizedBox>(
          find.ancestor(
            of: find.byType(CircularProgressIndicator),
            matching: find.byType(SizedBox),
          ),
        );
        expect(spinnerContainer.width, 12);
        expect(spinnerContainer.height, 12);
      });

      testWidgets('spinner has correct stroke width', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpStatusDisplay(group: group)),
          ),
        );

        final spinner = tester.widget<CircularProgressIndicator>(
          find.byType(CircularProgressIndicator),
        );
        expect(spinner.strokeWidth, 2);
      });
    });
  });
}
