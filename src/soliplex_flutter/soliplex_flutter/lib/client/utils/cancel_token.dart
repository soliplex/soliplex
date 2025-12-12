/// Token for cancelling async operations.
class CancelToken {
  bool _isCancelled = false;
  String? _reason;
  final List<void Function()> _listeners = [];

  /// Whether the token has been cancelled.
  bool get isCancelled => _isCancelled;

  /// The reason for cancellation, if any.
  String? get reason => _reason;

  /// Cancel the operation.
  void cancel([String? reason]) {
    if (_isCancelled) return;

    _isCancelled = true;
    _reason = reason;

    for (final listener in _listeners) {
      listener();
    }
    _listeners.clear();
  }

  /// Add a listener to be called when cancelled.
  void addListener(void Function() listener) {
    if (_isCancelled) {
      listener();
    } else {
      _listeners.add(listener);
    }
  }

  /// Remove a listener.
  void removeListener(void Function() listener) {
    _listeners.remove(listener);
  }

  /// Throw [CancelledException] if cancelled.
  void throwIfCancelled() {
    if (_isCancelled) {
      throw CancelledException(_reason);
    }
  }
}

/// Exception thrown when an operation is cancelled.
class CancelledException implements Exception {
  const CancelledException([this.reason]);

  final String? reason;

  @override
  String toString() {
    if (reason != null) {
      return 'CancelledException: $reason';
    }
    return 'CancelledException';
  }
}
