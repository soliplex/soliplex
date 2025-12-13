import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/connection_config.dart';
import '../utils/debug_log.dart';
import 'connection_events.dart' show SessionState;
import 'network_inspector.dart';
import 'room_session.dart';
import 'server_connection_state.dart';
import 'server_room_key.dart';

/// Top-level registry managing multiple server connections.
///
/// Provides:
/// - Multi-server support (connections to multiple servers simultaneously)
/// - Session pooling per server
/// - Automatic cleanup based on inactivity timeouts
/// - LRU eviction of backgrounded sessions
///
/// Usage:
/// ```dart
/// final registry = ref.read(connectionRegistryProvider);
/// final session = registry.getSession(ServerRoomKey(serverId: 'srv1', roomId: 'room1'));
/// ```
class ConnectionRegistry extends ChangeNotifier {
  final ConnectionConfig _config;
  final Map<String, ServerConnectionState> _servers = {};

  /// Network inspector for traffic capture (optional).
  final NetworkInspector? _inspector;

  /// Currently active server ID.
  String? _activeServerId;

  /// Currently active room ID.
  String? _activeRoomId;

  /// Cleanup timer for automatic disposal.
  Timer? _cleanupTimer;

  /// Whether the registry has been disposed.
  bool _disposed = false;

  /// Creates a new connection registry.
  ///
  /// [inspector] is optional network inspector for traffic capture.
  ConnectionRegistry({ConnectionConfig? config, NetworkInspector? inspector})
    : _config = config ?? ConnectionConfig.defaultConfig,
      _inspector = inspector {
    _startCleanupTimer();
    DebugLog.service('ConnectionRegistry: Created with config $_config');
  }

  // ==========================================================================
  // PUBLIC API
  // ==========================================================================

  /// Whether the registry has been disposed.
  bool get isDisposed => _disposed;

  /// The currently active server-room key, or null if none active.
  ServerRoomKey? get activeKey =>
      _activeServerId != null && _activeRoomId != null
      ? ServerRoomKey(serverId: _activeServerId!, roomId: _activeRoomId!)
      : null;

  /// The currently active server ID.
  String? get activeServerId => _activeServerId;

  /// The currently active room ID.
  String? get activeRoomId => _activeRoomId;

  /// Number of connected servers.
  int get serverCount => _servers.length;

  /// Total number of sessions across all servers.
  int get totalSessionCount =>
      _servers.values.fold(0, (sum, server) => sum + server.sessionCount);

  /// List of all connected server IDs.
  List<String> get serverIds => List.unmodifiable(_servers.keys.toList());

  /// Whether a server connection exists.
  bool hasServer(String serverId) => _servers.containsKey(serverId);

  /// Gets the state for a server, or null if not connected.
  ServerConnectionState? getServerState(String serverId) => _servers[serverId];

  /// Connects to a server or returns existing connection.
  ///
  /// If the server is already connected, returns the existing [ServerConnectionState].
  /// Otherwise creates a new connection.
  ///
  /// [headerRefresher] is called on 401 to refresh auth headers.
  ServerConnectionState connectServer(
    String serverId,
    String baseUrl, {
    Map<String, String>? headers,
    Future<Map<String, String>> Function()? headerRefresher,
  }) {
    _throwIfDisposed();

    var serverState = _servers[serverId];
    if (serverState != null) {
      serverState.touch();
      DebugLog.service(
        'ConnectionRegistry: Returning existing server $serverId',
      );
      return serverState;
    }

    serverState = ServerConnectionState(
      serverId: serverId,
      baseUrl: baseUrl,
      headers: headers,
      headerRefresher: headerRefresher,
      inspector: _inspector,
    );
    _servers[serverId] = serverState;

    DebugLog.service(
      'ConnectionRegistry: Connected to server $serverId ($baseUrl)',
    );
    notifyListeners();

    return serverState;
  }

  /// Gets a session by server-room key.
  ///
  /// Creates the server connection and/or session if they don't exist.
  /// This is the primary way to get sessions in the multi-connection architecture.
  ///
  /// [headerRefresher] is called on 401 to refresh auth headers.
  RoomSession getSession(
    ServerRoomKey key, {
    String? baseUrl,
    Map<String, String>? headers,
    Future<Map<String, String>> Function()? headerRefresher,
  }) {
    _throwIfDisposed();

    var serverState = _servers[key.serverId];
    if (serverState == null) {
      if (baseUrl == null) {
        throw StateError(
          'Server ${key.serverId} not connected and no baseUrl provided',
        );
      }
      serverState = connectServer(
        key.serverId,
        baseUrl,
        headers: headers,
        headerRefresher: headerRefresher,
      );
    }

    return serverState.getOrCreateSession(key.roomId);
  }

  /// Gets an existing session, or null if not found.
  RoomSession? getExistingSession(ServerRoomKey key) {
    return _servers[key.serverId]?.getSession(key.roomId);
  }

  /// Sets the active server and room.
  ///
  /// This is used to track which server/room the UI is currently showing.
  void setActive(ServerRoomKey key) {
    _throwIfDisposed();

    // Suspend previous active session if different
    if (_activeServerId != null && _activeRoomId != null) {
      final previousKey = ServerRoomKey(
        serverId: _activeServerId!,
        roomId: _activeRoomId!,
      );
      if (previousKey != key) {
        final previousSession = getExistingSession(previousKey);
        if (previousSession != null && previousSession.isActive) {
          previousSession.suspend();
        }
      }
    }

    _activeServerId = key.serverId;
    _activeRoomId = key.roomId;

    // Resume new active session
    final session = getExistingSession(key);
    if (session != null && session.state == SessionState.backgrounded) {
      session.resume();
    }

    // Update server's active room
    final serverState = _servers[key.serverId];
    if (serverState != null) {
      serverState.activeRoomId = key.roomId;

      // Evict old sessions if over limit
      final evicted = serverState.evictOldestBackgroundedSessions(
        _config.maxBackgroundedSessionsPerServer,
      );
      if (evicted > 0) {
        DebugLog.service(
          'ConnectionRegistry: Evicted $evicted backgrounded sessions',
        );
      }
    }

    DebugLog.service('ConnectionRegistry: Set active to $key');
    notifyListeners();
  }

  /// Focuses a specific server (sets it as active, no room change).
  void focusServer(String serverId) {
    _throwIfDisposed();

    if (!hasServer(serverId)) {
      throw StateError('Server $serverId not connected');
    }

    _activeServerId = serverId;
    _servers[serverId]?.touch();

    DebugLog.service('ConnectionRegistry: Focused server $serverId');
    notifyListeners();
  }

  /// Removes a server and disposes all its sessions.
  void removeServer(String serverId) {
    final serverState = _servers.remove(serverId);
    if (serverState != null) {
      serverState.dispose();
      DebugLog.service('ConnectionRegistry: Removed server $serverId');

      if (_activeServerId == serverId) {
        _activeServerId = null;
        _activeRoomId = null;
      }

      notifyListeners();
    }
  }

  /// Clears all servers and sessions.
  void clear() {
    DebugLog.service('ConnectionRegistry: Clearing all servers');

    for (final serverState in _servers.values) {
      serverState.dispose();
    }
    _servers.clear();

    _activeServerId = null;
    _activeRoomId = null;

    notifyListeners();
  }

  // ==========================================================================
  // CLEANUP
  // ==========================================================================

  void _startCleanupTimer() {
    if (_config.keepAlive) {
      DebugLog.service('ConnectionRegistry: Cleanup disabled (keepAlive=true)');
      return;
    }

    _cleanupTimer = Timer.periodic(_config.cleanupInterval, (_) {
      _performCleanup();
    });

    DebugLog.service(
      'ConnectionRegistry: Cleanup timer started (interval: ${_config.cleanupInterval})',
    );
  }

  void _performCleanup() {
    if (_disposed || _config.keepAlive) return;

    final now = DateTime.now();
    final serversToRemove = <String>[];

    for (final entry in _servers.entries) {
      final serverId = entry.key;
      final serverState = entry.value;

      // Check server-level timeout
      final serverAge = now.difference(serverState.lastActivity);
      if (serverAge > _config.serverInactivityTimeout) {
        DebugLog.service(
          'ConnectionRegistry: Server $serverId timed out (inactive for $serverAge)',
        );
        serversToRemove.add(serverId);
        continue;
      }

      // Check room-level timeouts within active servers
      final roomsToRemove = <String>[];
      for (final roomEntry in serverState.sessions.entries) {
        final roomId = roomEntry.key;
        final session = roomEntry.value;

        // Only timeout backgrounded sessions
        if (session.state != SessionState.backgrounded) continue;

        final sessionAge = session.lastActivity != null
            ? now.difference(session.lastActivity!)
            : Duration.zero;

        if (sessionAge > _config.roomInactivityTimeout) {
          DebugLog.service(
            'ConnectionRegistry: Session $serverId:$roomId timed out (inactive for $sessionAge)',
          );
          roomsToRemove.add(roomId);
        }
      }

      for (final roomId in roomsToRemove) {
        serverState.disposeSession(roomId);
      }
    }

    for (final serverId in serversToRemove) {
      removeServer(serverId);
    }
  }

  void _throwIfDisposed() {
    if (_disposed) {
      throw StateError('ConnectionRegistry has been disposed');
    }
  }

  @override
  void dispose() {
    if (_disposed) return;
    _disposed = true;

    DebugLog.service('ConnectionRegistry: Disposing');

    _cleanupTimer?.cancel();
    _cleanupTimer = null;

    for (final serverState in _servers.values) {
      serverState.dispose();
    }
    _servers.clear();

    super.dispose();
  }

  @override
  String toString() {
    return 'ConnectionRegistry(servers: $serverCount, sessions: $totalSessionCount, active: $activeKey)';
  }
}

/// Provider for the connection registry.
///
/// Singleton for app lifetime - manages all server connections.
/// Injects NetworkInspector for traffic capture.
///
/// NOTE: Uses ref.read for inspector (not watch) because the registry
/// should not be rebuilt when the inspector notifies listeners.
final connectionRegistryProvider = Provider<ConnectionRegistry>((ref) {
  final config = ref.watch(connectionConfigProvider);
  // Use read (not watch) - inspector changes shouldn't rebuild registry
  final inspector = ref.read(networkInspectorProvider);
  final registry = ConnectionRegistry(config: config, inspector: inspector);
  ref.onDispose(() => registry.dispose());
  return registry;
});

/// Provider for the currently active server-room key.
final activeServerRoomKeyProvider = Provider<ServerRoomKey?>((ref) {
  final registry = ref.watch(connectionRegistryProvider);
  return registry.activeKey;
});
