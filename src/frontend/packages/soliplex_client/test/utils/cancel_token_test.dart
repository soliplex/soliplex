import 'dart:async';

import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('CancelToken', () {
    group('initial state', () {
      test('isCancelled returns false', () {
        final token = CancelToken();
        expect(token.isCancelled, isFalse);
      });

      test('reason returns null', () {
        final token = CancelToken();
        expect(token.reason, isNull);
      });

      test('throwIfCancelled does not throw', () {
        final token = CancelToken();
        expect(token.throwIfCancelled, returnsNormally);
      });

      test('whenCancelled is not completed', () {
        final token = CancelToken();
        var completed = false;
        unawaited(token.whenCancelled.then((_) => completed = true));
        // Allow microtask to run
        expect(completed, isFalse);
      });
    });

    group('cancel', () {
      test('sets isCancelled to true', () {
        final token = CancelToken()..cancel();
        expect(token.isCancelled, isTrue);
      });

      test('without reason keeps reason as null', () {
        final token = CancelToken()..cancel();
        expect(token.reason, isNull);
      });

      test('with reason stores the reason', () {
        final token = CancelToken()..cancel('User navigated away');
        expect(token.reason, equals('User navigated away'));
      });

      test('completes whenCancelled future', () async {
        final token = CancelToken();
        var completed = false;
        unawaited(token.whenCancelled.then((_) => completed = true));

        token.cancel();

        // Allow future to complete
        await Future<void>.delayed(Duration.zero);
        expect(completed, isTrue);
      });

      test('multiple calls are idempotent', () {
        final token = CancelToken()
          ..cancel('First reason')
          ..cancel('Second reason');

        expect(token.isCancelled, isTrue);
        expect(token.reason, equals('First reason')); // First reason preserved
      });

      test('multiple calls do not complete whenCancelled multiple times', () {
        final token = CancelToken();
        var completionCount = 0;
        unawaited(token.whenCancelled.then((_) => completionCount++));

        token
          ..cancel()
          ..cancel()
          ..cancel();

        // The completer prevents multiple completions
        expect(completionCount, lessThanOrEqualTo(1));
      });
    });

    group('throwIfCancelled', () {
      test('throws CancelledException when cancelled', () {
        final token = CancelToken()..cancel();

        expect(
          token.throwIfCancelled,
          throwsA(isA<CancelledException>()),
        );
      });

      test('throws CancelledException with reason', () {
        final token = CancelToken()..cancel('Test reason');

        expect(
          token.throwIfCancelled,
          throwsA(
            isA<CancelledException>().having(
              (e) => e.reason,
              'reason',
              equals('Test reason'),
            ),
          ),
        );
      });

      test('does not throw when not cancelled', () {
        final token = CancelToken();
        expect(token.throwIfCancelled, returnsNormally);
      });
    });

    group('whenCancelled', () {
      test('completes when cancel is called', () async {
        final token = CancelToken();
        final completer = Completer<void>();

        unawaited(token.whenCancelled.then((_) => completer.complete()));

        expect(completer.isCompleted, isFalse);
        token.cancel();

        await Future<void>.delayed(Duration.zero);
        expect(completer.isCompleted, isTrue);
      });

      test('is immediately completed if already cancelled', () async {
        final token = CancelToken()..cancel();

        var completed = false;
        unawaited(token.whenCancelled.then((_) => completed = true));

        await Future<void>.delayed(Duration.zero);
        expect(completed, isTrue);
      });

      test('can be awaited multiple times', () async {
        final token = CancelToken();

        var count = 0;
        unawaited(token.whenCancelled.then((_) => count++));
        unawaited(token.whenCancelled.then((_) => count++));

        token.cancel();
        await Future<void>.delayed(Duration.zero);

        expect(count, equals(2));
      });
    });

    group('CancelledException', () {
      test('has correct message when cancelled without reason', () {
        final token = CancelToken()..cancel();

        try {
          token.throwIfCancelled();
          fail('Should have thrown');
        } on CancelledException catch (e) {
          expect(e.message, equals('Operation cancelled'));
        }
      });

      test('has correct message when cancelled with reason', () {
        final token = CancelToken()..cancel('User pressed cancel');

        try {
          token.throwIfCancelled();
          fail('Should have thrown');
        } on CancelledException catch (e) {
          expect(e.message, equals('User pressed cancel'));
        }
      });

      test('reason getter returns null for default message', () {
        const e = CancelledException();
        expect(e.reason, isNull);
      });

      test('reason getter returns custom reason', () {
        const e = CancelledException(reason: 'Custom reason');
        expect(e.reason, equals('Custom reason'));
      });
    });
  });
}
