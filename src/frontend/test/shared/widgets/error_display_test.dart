import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/shared/widgets/error_display.dart';

import '../../helpers/test_helpers.dart';

void main() {
  group('ErrorDisplay', () {
    testWidgets('displays network error message', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: const ErrorDisplay(
            error: NetworkException(message: 'Connection failed'),
          ),
        ),
      );

      expect(find.textContaining('Network error'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('displays not found error message', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: const ErrorDisplay(
            error: NotFoundException(message: 'Not found'),
          ),
        ),
      );

      expect(find.text('Resource not found.'), findsOneWidget);
    });

    testWidgets('displays API error message', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: const ErrorDisplay(
            error: ApiException(statusCode: 500, message: 'Server error'),
          ),
        ),
      );

      expect(find.textContaining('Server error (500)'), findsOneWidget);
    });

    testWidgets('displays generic error message', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: ErrorDisplay(
            error: Exception('Unknown error'),
          ),
        ),
      );

      expect(find.text('An unexpected error occurred.'), findsOneWidget);
    });

    testWidgets(
      'shows retry button when callback provided',
      (tester) async {
        var retryPressed = false;

        await tester.pumpWidget(
          createTestApp(
            home: ErrorDisplay(
              error: const NetworkException(message: 'Failed'),
              onRetry: () => retryPressed = true,
            ),
          ),
        );

        expect(find.text('Retry'), findsOneWidget);

        await tester.tap(find.text('Retry'));
        await tester.pump();

        expect(retryPressed, true);
      },
    );

    testWidgets(
      'hides retry button when callback not provided',
      (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const ErrorDisplay(
              error: NetworkException(message: 'Failed'),
            ),
          ),
        );

        expect(find.text('Retry'), findsNothing);
      },
    );
  });
}
