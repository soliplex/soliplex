import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart' show NetworkException;
import 'package:soliplex_frontend/features/inspector/models/http_event_group.dart';
import 'package:soliplex_frontend/features/inspector/widgets/http_event_tile.dart';

import '../../../helpers/test_helpers.dart';

void main() {
  group('HttpEventTile', () {
    group('Request display', () {
      testWidgets('displays method and path', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpEventTile(group: group)),
          ),
        );

        expect(find.text('GET'), findsOneWidget);
        expect(find.text('/api/v1/rooms'), findsOneWidget);
      });

      testWidgets('displays timestamp', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(
            timestamp: DateTime(2024, 1, 15, 10, 30, 45),
          ),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpEventTile(group: group)),
          ),
        );

        expect(find.text('10:30:45'), findsOneWidget);
      });

      testWidgets('displays query parameters in path', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(
            uri: Uri.parse('http://localhost/api/rooms?limit=50&offset=100'),
          ),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpEventTile(group: group)),
          ),
        );

        expect(find.text('/api/rooms?limit=50&offset=100'), findsOneWidget);
      });

      testWidgets('shows pending status when no response', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpEventTile(group: group)),
          ),
        );

        expect(find.text('pending...'), findsOneWidget);
        final semantics = tester.getSemantics(find.byType(HttpEventTile));
        expect(semantics.label, contains('pending'));
      });
    });

    group('Success response', () {
      testWidgets('displays status, duration, and size', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpEventTile(group: group)),
          ),
        );

        expect(find.text('200 OK (45ms, 1.2KB)'), findsOneWidget);
      });

      testWidgets('shows success status when response received',
          (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpEventTile(group: group)),
          ),
        );

        expect(find.text('pending...'), findsNothing);
        final semantics = tester.getSemantics(find.byType(HttpEventTile));
        expect(semantics.label, contains('success'));
      });
    });

    group('Client error response', () {
      testWidgets('displays 4xx status', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 404),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpEventTile(group: group)),
          ),
        );

        expect(find.text('404 (45ms)'), findsOneWidget);
      });
    });

    group('Server error response', () {
      testWidgets('displays 5xx status', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 500),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpEventTile(group: group)),
          ),
        );

        expect(find.text('500 (45ms)'), findsOneWidget);
      });
    });

    group('Network error', () {
      testWidgets('displays exception type and duration', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          error: TestData.createErrorEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpEventTile(group: group)),
          ),
        );

        expect(find.text('POST'), findsOneWidget);
        expect(find.text('/api/v1/threads'), findsOneWidget);
        expect(find.text('NetworkException (2.0s)'), findsOneWidget);
      });
    });

    group('SSE streaming', () {
      testWidgets('displays SSE indicator with path', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpEventTile(group: group)),
          ),
        );

        expect(find.text('SSE'), findsOneWidget);
        expect(find.text('/api/v1/runs/run-1/stream'), findsOneWidget);
      });

      testWidgets('shows streaming status when active', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpEventTile(group: group)),
          ),
        );

        expect(find.text('streaming...'), findsOneWidget);
        final semantics = tester.getSemantics(find.byType(HttpEventTile));
        expect(semantics.label, contains('streaming'));
      });

      testWidgets('shows complete status when stream ends', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
          streamEnd: TestData.createStreamEndEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpEventTile(group: group)),
          ),
        );

        expect(find.text('complete (10.0s, 5.1KB)'), findsOneWidget);
      });

      testWidgets('shows error status when stream fails', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
          streamEnd: TestData.createStreamEndEvent(
            error: const NetworkException(message: 'Connection lost'),
          ),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpEventTile(group: group)),
          ),
        );

        expect(find.text('error (10.0s)'), findsOneWidget);
      });
    });

    group('Accessibility', () {
      testWidgets('provides semantic label for pending request',
          (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpEventTile(group: group)),
          ),
        );

        final semantics = tester.getSemantics(find.byType(HttpEventTile));
        expect(semantics.label, contains('GET request'));
        expect(semantics.label, contains('pending'));
      });

      testWidgets('provides semantic label for success response',
          (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpEventTile(group: group)),
          ),
        );

        final semantics = tester.getSemantics(find.byType(HttpEventTile));
        expect(semantics.label, contains('success'));
        expect(semantics.label, contains('200'));
      });

      testWidgets('provides semantic label for error', (tester) async {
        final group = HttpEventGroup(
          requestId: 'req-1',
          error: TestData.createErrorEvent(),
        );

        await tester.pumpWidget(
          createTestApp(
            home: Scaffold(body: HttpEventTile(group: group)),
          ),
        );

        final semantics = tester.getSemantics(find.byType(HttpEventTile));
        expect(semantics.label, contains('network error'));
      });
    });
  });
}
