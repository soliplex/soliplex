import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/core/utils/update_throttler.dart';

void main() {
  group('UpdateThrottler', () {
    test('emits first update immediately', () {
      var updates = 0;
      final throttler = UpdateThrottler(
        duration: const Duration(milliseconds: 50),
        onUpdate: () => updates++,
      );

      throttler.notify();
      expect(updates, equals(1));
    });

    test('throttles subsequent updates', () async {
      var updates = 0;
      final throttler = UpdateThrottler(
        duration: const Duration(milliseconds: 50),
        onUpdate: () => updates++,
      );

      throttler.notify(); // Immediate
      expect(updates, equals(1));

      throttler.notify(); // Buffered
      throttler.notify(); // Buffered
      expect(updates, equals(1));

      await Future<void>.delayed(const Duration(milliseconds: 25));
      throttler.notify(); // Still buffered
      expect(updates, equals(1));

      await Future<void>.delayed(
        const Duration(milliseconds: 30),
      ); // Total > 50ms
      expect(updates, equals(2)); // Trailing update
    });

    test('force update bypasses throttle', () async {
      var updates = 0;
      final throttler = UpdateThrottler(
        duration: const Duration(milliseconds: 50),
        onUpdate: () => updates++,
      );

      throttler.notify(); // Immediate
      expect(updates, equals(1));

      throttler.notify(force: true); // Immediate force
      expect(updates, equals(2));

      // Timer should have been reset/cancelled by force
      throttler.notify();
      expect(updates, equals(2)); // Buffering

      await Future<void>.delayed(const Duration(milliseconds: 60));
      expect(updates, equals(3));
    });

    test('trailing update includes latest state', () async {
      var counter = 0;
      final throttler = UpdateThrottler(
        duration: const Duration(milliseconds: 50),
        onUpdate: () => counter++,
      );

      throttler.notify();
      expect(counter, equals(1));

      await Future<void>.delayed(const Duration(milliseconds: 10));
      throttler.notify(); // Schedule trailing

      await Future<void>.delayed(const Duration(milliseconds: 50));
      expect(counter, equals(2));
    });
  });
}
