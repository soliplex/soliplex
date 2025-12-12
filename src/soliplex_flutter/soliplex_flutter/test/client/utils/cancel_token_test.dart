import 'package:soliplex_flutter/client/utils/cancel_token.dart';
import 'package:test/test.dart';

void main() {
  group('CancelToken', () {
    test('starts not cancelled', () {
      final token = CancelToken();

      expect(token.isCancelled, isFalse);
      expect(token.reason, isNull);
    });

    test('can be cancelled without reason', () {
      final token = CancelToken();
      token.cancel();

      expect(token.isCancelled, isTrue);
      expect(token.reason, isNull);
    });

    test('can be cancelled with reason', () {
      final token = CancelToken();
      token.cancel('User requested');

      expect(token.isCancelled, isTrue);
      expect(token.reason, 'User requested');
    });

    test('cancel is idempotent', () {
      final token = CancelToken();
      token.cancel('First');
      token.cancel('Second');

      expect(token.isCancelled, isTrue);
      expect(token.reason, 'First');
    });

    test('listeners are called on cancel', () {
      final token = CancelToken();
      var called = false;

      token.addListener(() => called = true);
      expect(called, isFalse);

      token.cancel();
      expect(called, isTrue);
    });

    test('listener added after cancel is called immediately', () {
      final token = CancelToken();
      token.cancel();

      var called = false;
      token.addListener(() => called = true);

      expect(called, isTrue);
    });

    test('listeners are cleared after cancel', () {
      final token = CancelToken();
      var callCount = 0;

      token.addListener(() => callCount++);
      token.cancel();
      token.cancel(); // Second cancel should not call listener

      expect(callCount, 1);
    });

    test('removeListener removes listener', () {
      final token = CancelToken();
      var called = false;

      void listener() => called = true;

      token.addListener(listener);
      token.removeListener(listener);
      token.cancel();

      expect(called, isFalse);
    });

    test('throwIfCancelled does nothing when not cancelled', () {
      final token = CancelToken();

      expect(() => token.throwIfCancelled(), returnsNormally);
    });

    test('throwIfCancelled throws when cancelled', () {
      final token = CancelToken();
      token.cancel('Test');

      expect(
        () => token.throwIfCancelled(),
        throwsA(isA<CancelledException>()),
      );
    });
  });

  group('CancelledException', () {
    test('toString without reason', () {
      const exception = CancelledException();

      expect(exception.toString(), 'CancelledException');
    });

    test('toString with reason', () {
      const exception = CancelledException('User cancelled');

      expect(exception.toString(), 'CancelledException: User cancelled');
    });
  });
}
