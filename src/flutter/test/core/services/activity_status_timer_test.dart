import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/core/models/activity_status_config.dart';
import 'package:soliplex/core/services/activity_status_service.dart';

/// Tests for ActivityStatusNotifier timer race condition fix.
///
/// These tests verify that timers do not corrupt state after disposal,
/// which can happen during rapid room switching when Riverpod invalidates
/// providers asynchronously but Dart timers fire synchronously.
void main() {
  late ActivityStatusNotifier notifier;
  late ActivityStatusConfig config;
  var disposed = false;

  setUp(() {
    disposed = false;
    config = const ActivityStatusConfig(
      initialDelay: Duration(milliseconds: 100),
      cycleInterval: Duration(milliseconds: 200),
      idleMessages: ['Message 1', 'Message 2', 'Message 3'],
    );
    notifier = ActivityStatusNotifier(
      config: config,
      serverId: 'test-server',
      roomId: 'test-room',
    );
  });

  tearDown(() {
    if (!disposed) {
      notifier.dispose();
      disposed = true;
    }
  });

  group('Timer Race Condition Prevention', () {
    test('timer callback does not execute after dispose', () {
      fakeAsync((async) {
        // Start activity (sets up initial delay timer)
        notifier.startActivity();

        // Dispose BEFORE timer fires
        notifier.dispose();
        disposed = true;

        // Advance past the initial delay
        async.elapse(const Duration(milliseconds: 200));

        // No crash = success (timer was guarded by _isDisposed)
      });
    });

    test('cycle timer callback does not execute after dispose', () {
      fakeAsync((async) {
        // Start activity and advance past initial delay
        notifier.startActivity();
        async.elapse(const Duration(milliseconds: 150));

        // Now activity should be active
        expect(notifier.state.isActive, isTrue);

        // Dispose before next cycle
        notifier.dispose();
        disposed = true;

        // Advance past multiple cycle intervals
        async.elapse(const Duration(seconds: 1));

        // No crash = success (timer was guarded by _isDisposed)
      });
    });

    test('injected message timer does not execute after dispose', () {
      fakeAsync((async) {
        // Inject message with duration
        notifier.injectMessage(
          'Test Message',
          duration: const Duration(milliseconds: 500),
        );

        expect(notifier.state.currentMessage, equals('Test Message'));

        // Dispose before injected message timer fires
        notifier.dispose();
        disposed = true;

        // Advance past the duration
        async.elapse(const Duration(seconds: 1));

        // No crash = success (timer was guarded)
      });
    });

    test('rapid start/dispose does not cause timer leaks', () {
      fakeAsync((async) {
        // Dispose the setUp notifier first since we're creating our own
        notifier.dispose();
        disposed = true;

        // Simulate rapid room switching: create/dispose 100 times
        for (var i = 0; i < 100; i++) {
          final tempNotifier = ActivityStatusNotifier(
            config: config,
            serverId: 'server',
            roomId: 'room-$i',
          );

          tempNotifier.startActivity();
          tempNotifier.dispose();
        }

        // Advance way past any possible timer
        async.elapse(const Duration(hours: 1));

        // No crashes, no leaked timers = success
      });
    });

    test('dispose during active cycling does not crash', () {
      fakeAsync((async) {
        notifier.startActivity();

        // Advance to start cycling
        async.elapse(const Duration(milliseconds: 150));

        // Let it cycle a few times
        async.elapse(const Duration(milliseconds: 500));

        // Dispose mid-cycle
        notifier.dispose();
        disposed = true;

        // Advance more
        async.elapse(const Duration(seconds: 2));

        // No crash = success
      });
    });

    test('methods are no-op after dispose', () {
      fakeAsync((async) {
        notifier.dispose();
        disposed = true;

        // These should all be no-ops (guards check _isDisposed)
        notifier.startActivity();
        notifier.stopActivity();
        notifier.handleEvent(eventType: 'RUN_STARTED');
        notifier.injectMessage('Test');

        // Advance time
        async.elapse(const Duration(seconds: 1));

        // No crash = success (all methods guarded by _isDisposed)
      });
    });
  });

  group('Timer Behavior Without Race', () {
    test('initial delay timer shows message after delay', () {
      fakeAsync((async) {
        expect(notifier.state.isActive, isFalse);

        notifier.startActivity();

        // Before delay
        async.elapse(const Duration(milliseconds: 50));
        expect(notifier.state.isActive, isFalse);

        // After delay
        async.elapse(const Duration(milliseconds: 100));
        expect(notifier.state.isActive, isTrue);
        expect(notifier.state.currentMessage, isNotNull);

        // Must dispose inside fakeAsync since timers were created here
        notifier.dispose();
        disposed = true;
      });
    });

    test('cycle timer updates messages periodically', () {
      fakeAsync((async) {
        notifier.startActivity();

        // Advance past initial delay
        async.elapse(const Duration(milliseconds: 150));

        final firstIndex = notifier.state.messageIndex;

        // Advance one cycle
        async.elapse(const Duration(milliseconds: 200));

        // Should have advanced to next message
        expect(notifier.state.messageIndex, greaterThan(firstIndex));

        // Must dispose inside fakeAsync since timers were created here
        notifier.dispose();
        disposed = true;
      });
    });

    test('stopActivity cancels all timers', () {
      fakeAsync((async) {
        notifier.startActivity();
        async.elapse(const Duration(milliseconds: 150));

        expect(notifier.state.isActive, isTrue);

        notifier.stopActivity();

        expect(notifier.state.isActive, isFalse);

        // Advance time - no more updates should happen
        final stateAfterStop = notifier.state;
        async.elapse(const Duration(seconds: 1));

        expect(notifier.state, equals(stateAfterStop));

        // Must dispose inside fakeAsync since timers were created here
        notifier.dispose();
        disposed = true;
      });
    });

    test('injected message returns to cycling after duration', () {
      fakeAsync((async) {
        // Start activity first
        notifier.startActivity();
        async.elapse(const Duration(milliseconds: 150));

        // Inject a custom message
        notifier.injectMessage(
          'Custom Injection',
          duration: const Duration(milliseconds: 300),
        );

        expect(notifier.state.currentMessage, equals('Custom Injection'));

        // After duration, should show next cycling message (not original)
        async.elapse(const Duration(milliseconds: 350));

        expect(
          notifier.state.currentMessage,
          isNot(equals('Custom Injection')),
        );
        expect(notifier.state.isActive, isTrue);

        // Must dispose inside fakeAsync since timers were created here
        notifier.dispose();
        disposed = true;
      });
    });
  });

  group('Event Context Updates', () {
    test('handleEvent updates context', () {
      fakeAsync((async) {
        notifier.startActivity();
        async.elapse(const Duration(milliseconds: 150));

        notifier.handleEvent(eventType: 'TOOL_CALL_START', toolName: 'search');

        expect(notifier.state.currentEventType, equals('TOOL_CALL_START'));
        expect(notifier.state.currentToolName, equals('search'));

        // Must dispose inside fakeAsync since timers were created here
        notifier.dispose();
        disposed = true;
      });
    });

    test('handleEvent clears toolName when null', () {
      fakeAsync((async) {
        notifier.startActivity();
        async.elapse(const Duration(milliseconds: 150));

        // First set a tool name
        notifier.handleEvent(eventType: 'TOOL_CALL_START', toolName: 'search');
        expect(notifier.state.currentToolName, equals('search'));

        // Then clear it
        notifier.handleEvent(eventType: 'TOOL_CALL_END');
        expect(notifier.state.currentToolName, isNull);

        // Must dispose inside fakeAsync since timers were created here
        notifier.dispose();
        disposed = true;
      });
    });
  });
}
