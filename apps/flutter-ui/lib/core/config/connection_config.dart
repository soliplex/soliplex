// reason: mutable data class pattern
// ignore_for_file: avoid_equals_and_hash_code_on_mutable_classes
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Configuration for multi-connection behavior.
///
/// Controls timeouts, session limits, and cleanup behavior for the
/// ConnectionRegistry and its managed sessions.
class ConnectionConfig {
  /// Creates a connection configuration.
  const ConnectionConfig({
    this.roomInactivityTimeout = const Duration(hours: 24),
    this.serverInactivityTimeout = const Duration(days: 7),
    this.maxBackgroundedSessionsPerServer = 5,
    this.cleanupInterval = const Duration(minutes: 5),
    this.keepAlive = false,
  });

  /// Timeout for backgrounded room sessions.
  ///
  /// Sessions in the `backgrounded` state will be disposed after this
  /// duration of inactivity. Default: 24 hours.
  ///
  /// Active or streaming sessions are never subject to this timeout.
  final Duration roomInactivityTimeout;

  /// Timeout for inactive server connections.
  ///
  /// Server connections with no activity will be disposed after this
  /// duration. All rooms under the server are disposed. Default: 7 days.
  final Duration serverInactivityTimeout;

  /// Maximum number of backgrounded sessions per server before LRU eviction.
  ///
  /// When switching rooms, if this limit is exceeded, the oldest
  /// backgrounded session will be evicted. Default: 5.
  final int maxBackgroundedSessionsPerServer;

  /// Interval for the cleanup timer.
  ///
  /// The registry periodically checks for sessions/servers to dispose
  /// based on inactivity timeouts. Default: 5 minutes.
  final Duration cleanupInterval;

  /// Whether to disable all automatic cleanup.
  ///
  /// When true, sessions and servers are never automatically disposed.
  /// Useful for debugging or when manual lifecycle control is needed.
  final bool keepAlive;

  /// Default configuration with reasonable production values.
  static const ConnectionConfig defaultConfig = ConnectionConfig();

  /// Configuration that never cleans up sessions (for testing/debugging).
  static const ConnectionConfig noCleanup = ConnectionConfig(keepAlive: true);

  /// Configuration with aggressive cleanup (for memory-constrained
  /// environments).
  static const ConnectionConfig aggressive = ConnectionConfig(
    roomInactivityTimeout: Duration(minutes: 30),
    serverInactivityTimeout: Duration(hours: 1),
    maxBackgroundedSessionsPerServer: 2,
    cleanupInterval: Duration(minutes: 1),
  );

  /// Creates a copy with optionally updated fields.
  ConnectionConfig copyWith({
    Duration? roomInactivityTimeout,
    Duration? serverInactivityTimeout,
    int? maxBackgroundedSessionsPerServer,
    Duration? cleanupInterval,
    bool? keepAlive,
  }) {
    return ConnectionConfig(
      roomInactivityTimeout:
          roomInactivityTimeout ?? this.roomInactivityTimeout,
      serverInactivityTimeout:
          serverInactivityTimeout ?? this.serverInactivityTimeout,
      maxBackgroundedSessionsPerServer:
          maxBackgroundedSessionsPerServer ??
          this.maxBackgroundedSessionsPerServer,
      cleanupInterval: cleanupInterval ?? this.cleanupInterval,
      keepAlive: keepAlive ?? this.keepAlive,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ConnectionConfig &&
          runtimeType == other.runtimeType &&
          roomInactivityTimeout == other.roomInactivityTimeout &&
          serverInactivityTimeout == other.serverInactivityTimeout &&
          maxBackgroundedSessionsPerServer ==
              other.maxBackgroundedSessionsPerServer &&
          cleanupInterval == other.cleanupInterval &&
          keepAlive == other.keepAlive;

  @override
  int get hashCode => Object.hash(
    roomInactivityTimeout,
    serverInactivityTimeout,
    maxBackgroundedSessionsPerServer,
    cleanupInterval,
    keepAlive,
  );

  @override
  String toString() {
    return 'ConnectionConfig('
        'roomInactivity: $roomInactivityTimeout, '
        'serverInactivity: $serverInactivityTimeout, '
        'maxBackgrounded: $maxBackgroundedSessionsPerServer, '
        'cleanup: $cleanupInterval, '
        'keepAlive: $keepAlive)';
  }
}

/// Provider for connection configuration.
///
/// Override this provider to customize connection behavior:
/// ```dart
/// ProviderScope(
///   overrides: [
///     connectionConfigProvider.overrideWithValue(
///       ConnectionConfig(roomInactivityTimeout: Duration(hours: 1)),
///     ),
///   ],
///   child: MyApp(),
/// )
/// ```
final connectionConfigProvider = Provider<ConnectionConfig>((ref) {
  return ConnectionConfig.defaultConfig;
});
