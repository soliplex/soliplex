import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/network/connection_events.dart';
import 'package:soliplex/core/network/connection_manager.dart';

/// Read-only observer for network connection state.
///
/// Provides visibility into:
/// - Active connections across rooms
/// - Connection events (start, complete, cancel, error)
/// - Real-time status updates
class NetworkObserver {
  NetworkObserver(this._manager, {this.maxEventHistory = 100}) {
    _subscription = _manager.events.listen(_onEvent);
  }
  final ConnectionManager _manager;
  final List<ConnectionEvent> _eventHistory = [];
  final int maxEventHistory;

  StreamSubscription<ConnectionEvent>? _subscription;

  void _onEvent(ConnectionEvent event) {
    _eventHistory.add(event);

    // Trim history
    while (_eventHistory.length > maxEventHistory) {
      _eventHistory.removeAt(0);
    }
  }

  /// Currently active room ID.
  String? get activeRoomId => _manager.activeRoomId;

  /// All connection info.
  List<ConnectionInfo> get connections => _manager.activeConnections;

  /// Get connections that are currently streaming.
  List<ConnectionInfo> get streamingConnections =>
      connections.where((c) => c.isStreaming).toList();

  /// Get connections that are active (not backgrounded or disposed).
  List<ConnectionInfo> get activeConnections =>
      connections.where((c) => c.isActive).toList();

  /// Get connections that are backgrounded.
  List<ConnectionInfo> get backgroundedConnections =>
      connections.where((c) => c.state == SessionState.backgrounded).toList();

  /// Recent event history.
  List<ConnectionEvent> get eventHistory => List.unmodifiable(_eventHistory);

  /// Stream of connection events.
  Stream<ConnectionEvent> get events => _manager.events;

  /// Get info for a specific room.
  ConnectionInfo? getConnectionInfo(String roomId) =>
      _manager.getConnectionInfo(roomId);

  /// Check if any room is currently streaming.
  bool get hasActiveStream => streamingConnections.isNotEmpty;

  /// Get summary stats.
  NetworkStats get stats => NetworkStats(
    totalConnections: connections.length,
    activeCount: activeConnections.length,
    streamingCount: streamingConnections.length,
    backgroundedCount: backgroundedConnections.length,
    totalEvents: _eventHistory.length,
  );

  void dispose() {
    _subscription?.cancel();
  }
}

/// Summary statistics for network state.
class NetworkStats {
  const NetworkStats({
    required this.totalConnections,
    required this.activeCount,
    required this.streamingCount,
    required this.backgroundedCount,
    required this.totalEvents,
  });
  final int totalConnections;
  final int activeCount;
  final int streamingCount;
  final int backgroundedCount;
  final int totalEvents;

  @override
  String toString() =>
      // ignore: lines_longer_than_80_chars (auto-documented)
      'NetworkStats(total: $totalConnections, active: $activeCount, streaming: $streamingCount, bg: $backgroundedCount)';
}

/// Riverpod provider for NetworkObserver.
final networkObserverProvider = Provider<NetworkObserver>((ref) {
  final manager = ref.watch(connectionManagerProvider);
  final observer = NetworkObserver(manager);
  ref.onDispose(observer.dispose);
  return observer;
});

/// Provider for NetworkObserver with specific ConnectionManager.
final ProviderFamily<NetworkObserver, ConnectionManager>
networkObserverWithManagerProvider =
    Provider.family<NetworkObserver, ConnectionManager>((ref, manager) {
      final observer = NetworkObserver(manager);
      ref.onDispose(observer.dispose);
      return observer;
    });
