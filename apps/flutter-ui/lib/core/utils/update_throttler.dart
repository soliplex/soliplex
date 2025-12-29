import 'dart:async';

/// Helper to throttle UI updates.
///
/// Ensures updates are emitted at most once every [duration],
/// while guaranteeing the first update is immediate and the final
/// update is eventually sent.
class UpdateThrottler {
  UpdateThrottler({required this.duration, required this.onUpdate});
  final Duration duration;
  final void Function() onUpdate;

  DateTime? _lastUpdate;
  Timer? _timer;

  /// Notify that an update is available.
  ///
  /// If [force] is true, the update is emitted immediately, cancelling
  /// any pending throttled update.
  void notify({bool force = false}) {
    if (force) {
      _emit();
      return;
    }

    final now = DateTime.now();
    if (_lastUpdate == null || now.difference(_lastUpdate!) >= duration) {
      _emit();
    } else {
      // Schedule trailing update if not already scheduled
      if (_timer == null) {
        final wait = duration - now.difference(_lastUpdate!);
        _timer = Timer(wait, _emit);
      }
    }
  }

  void _emit() {
    _timer?.cancel();
    _timer = null;
    _lastUpdate = DateTime.now();
    onUpdate();
  }

  void dispose() {
    _timer?.cancel();
  }
}
