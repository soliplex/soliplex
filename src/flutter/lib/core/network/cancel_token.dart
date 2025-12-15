import 'dart:async';

/// Token for cancelling network operations.
///
/// Pass this to network operations and call [cancel] to abort them.
/// Operations should check [isCancelled] or listen to [onCancel].
class CancelToken {
  final Completer<void> _completer = Completer<void>();
  bool _isCancelled = false;
  String? _cancelReason;

  /// Whether the token has been cancelled.
  bool get isCancelled => _isCancelled;

  /// The reason for cancellation, if provided.
  String? get cancelReason => _cancelReason;

  /// Future that completes when the token is cancelled.
  Future<void> get onCancel => _completer.future;

  /// Cancel all operations using this token.
  void cancel([String? reason]) {
    if (_isCancelled) return;
    _isCancelled = true;
    _cancelReason = reason;
    if (!_completer.isCompleted) {
      _completer.complete();
    }
  }

  /// Throw CancelledException if the token is cancelled.
  void throwIfCancelled() {
    if (_isCancelled) {
      throw CancelledException(_cancelReason);
    }
  }
}

/// Exception thrown when an operation is cancelled.
class CancelledException implements Exception {
  CancelledException([this.reason]);
  final String? reason;

  @override
  String toString() =>
      reason != null ? 'CancelledException: $reason' : 'CancelledException';
}

/// Exception thrown when an SSE stream times out (no events received).
///
/// This is distinct from CancelledException which is user-initiated.
/// StreamTimeoutException indicates the server stopped responding.
class StreamTimeoutException implements Exception {
  StreamTimeoutException(this.message, this.timeout);
  final String message;
  final Duration timeout;

  @override
  String toString() => 'StreamTimeoutException: $message (timeout: $timeout)';
}
