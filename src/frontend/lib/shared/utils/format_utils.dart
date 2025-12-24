/// Utility extensions for HTTP inspector display formatting.
library;

/// Extension on [DateTime] for HTTP inspector timestamp display.
extension HttpTimestampFormat on DateTime {
  /// Formats as HH:MM:SS with zero padding for HTTP event timestamps.
  String toHttpTimeString() {
    final h = hour.toString().padLeft(2, '0');
    final m = minute.toString().padLeft(2, '0');
    final s = second.toString().padLeft(2, '0');
    return '$h:$m:$s';
  }
}

/// Extension on [Duration] for HTTP inspector duration display.
extension HttpDurationFormat on Duration {
  static const _msPerSecond = 1000;
  static const _msPerMinute = 60000;

  /// Formats duration as a human-readable string for HTTP inspector.
  ///
  /// Returns:
  /// - "Xms" for durations under 1 second
  /// - "X.Xs" for durations under 1 minute
  /// - "X.Xm" for longer durations
  String toHttpDurationString() {
    final ms = inMilliseconds;
    if (ms < _msPerSecond) return '${ms}ms';
    if (ms < _msPerMinute) return '${(ms / _msPerSecond).toStringAsFixed(1)}s';
    return '${(ms / _msPerMinute).toStringAsFixed(1)}m';
  }
}

/// Extension on [int] for HTTP inspector byte size display.
extension HttpBytesFormat on int {
  static const _bytesPerKB = 1024;
  static const _bytesPerMB = 1024 * 1024;

  /// Formats byte count as a human-readable string for HTTP inspector.
  ///
  /// Returns:
  /// - "XB" for sizes under 1KB
  /// - "X.XKB" for sizes under 1MB
  /// - "X.XMB" for larger sizes
  String toHttpBytesString() {
    if (this < _bytesPerKB) return '${this}B';
    if (this < _bytesPerMB) {
      return '${(this / _bytesPerKB).toStringAsFixed(1)}KB';
    }
    return '${(this / _bytesPerMB).toStringAsFixed(1)}MB';
  }
}
