import 'dart:async';

/// A fake clock for testing time-dependent code.
///
/// Allows manual control of time progression for testing:
/// - Timers
/// - Timeouts
/// - Inactivity tracking
class FakeClock {
  FakeClock([DateTime? initial]) : _now = initial ?? DateTime(2024);
  DateTime _now;
  final List<_FakeTimer> _timers = [];

  /// Current fake time.
  DateTime get now => _now;

  /// Advances time by [duration] and fires any elapsed timers.
  void advance(Duration duration) {
    _now = _now.add(duration);
    _fireElapsedTimers();
  }

  /// Sets the clock to a specific time and fires any elapsed timers.
  void setTime(DateTime time) {
    _now = time;
    _fireElapsedTimers();
  }

  /// Creates a timer that will fire after [duration] relative to fake time.
  Timer createTimer(Duration duration, void Function() callback) {
    final timer = _FakeTimer(
      fireAt: _now.add(duration),
      callback: callback,
    );
    _timers.add(timer);
    return timer;
  }

  /// Creates a periodic timer.
  Timer createPeriodicTimer(Duration period, void Function(Timer) callback) {
    final timer = _FakeTimer(
      fireAt: _now.add(period),
      periodicCallback: callback,
      periodic: true,
      period: period,
    );
    _timers.add(timer);
    return timer;
  }

  void _fireElapsedTimers() {
    // Process timers in order of fire time
    _timers.sort((a, b) => a.fireAt.compareTo(b.fireAt));

    final toRemove = <_FakeTimer>[];

    for (final timer in _timers) {
      if (!timer.isActive) {
        toRemove.add(timer);
        continue;
      }

      while (timer.isActive && !timer.fireAt.isAfter(_now)) {
        timer.fire();

        if (timer.periodic && timer.isActive) {
          timer.fireAt = timer.fireAt.add(timer.period!);
        } else {
          toRemove.add(timer);
          break;
        }
      }
    }

    for (final timer in toRemove) {
      _timers.remove(timer);
    }
  }

  /// Cancels all timers.
  void reset() {
    for (final timer in _timers) {
      timer.cancel();
    }
    _timers.clear();
  }
}

class _FakeTimer implements Timer {
  _FakeTimer({
    required this.fireAt,
    this.callback,
    this.periodicCallback,
    this.periodic = false,
    this.period,
  });
  DateTime fireAt;
  final void Function()? callback;
  final void Function(Timer)? periodicCallback;
  final bool periodic;
  final Duration? period;
  bool _isActive = true;
  int _tick = 0;

  @override
  bool get isActive => _isActive;

  @override
  int get tick => _tick;

  @override
  void cancel() {
    _isActive = false;
  }

  void fire() {
    if (!_isActive) return;
    _tick++;

    if (periodic) {
      periodicCallback?.call(this);
    } else {
      callback?.call();
      _isActive = false;
    }
  }
}

/// Extension to make DateTime testable with FakeClock.
extension FakeClockDateTime on FakeClock {
  /// Returns true if [duration] has passed since [since].
  bool hasElapsed(Duration duration, {required DateTime since}) {
    return now.difference(since) >= duration;
  }
}
