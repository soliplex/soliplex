import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/core/models/endpoint_models.dart';
import 'package:soliplex/core/network/connection_events.dart';
import 'package:soliplex/core/network/connection_registry.dart';
import 'package:soliplex/core/network/room_event_handler.dart';
import 'package:soliplex/core/network/room_session.dart';
import 'package:soliplex/core/network/server_connection_state.dart';
import 'package:soliplex/core/network/server_room_key.dart';
import 'package:soliplex/core/protocol/chat_session.dart';
import 'package:soliplex/core/providers/app_providers.dart';
import 'package:soliplex/core/providers/panel_providers.dart';
import 'package:soliplex/core/services/local_tools_service.dart';
import 'package:soliplex/core/utils/debug_log.dart';

/// Local tool execution notifier callback type.
typedef LocalToolNotifier =
    void Function(String toolCallId, String toolName, String status);

/// Callback to refresh auth headers on 401.
typedef HeaderRefresher = Future<Map<String, String>> Function(String serverId);

/// Facade over ConnectionRegistry for backward compatibility.
class ConnectionManager extends ChangeNotifier {
  ConnectionManager({
    ConnectionRegistry? registry,
    String baseUrl = '',
    Map<String, String>? headers,
    HeaderRefresher? headerRefresher,
  }) : _registry = registry ?? ConnectionRegistry(),
       _headerRefresher = headerRefresher {
    _registry.addListener(_onRegistryChanged);
    if (baseUrl.isNotEmpty) {
      switchServer(baseUrl, headers: headers);
    }
  }

  /// Connection registry for multi-server support.
  final ConnectionRegistry _registry;

  /// Callback to refresh auth headers on 401.
  final HeaderRefresher? _headerRefresher;

  /// Currently active server ID.
  String? _activeServerId;

  /// Event stream for all sessions.
  final StreamController<ConnectionEvent> _eventController =
      StreamController<ConnectionEvent>.broadcast();

  /// Track if manager is disposed to prevent updates after disposal.
  bool _disposed = false;

  /// Whether the manager has been configured with a server.
  bool get isConfigured =>
      _activeServerId != null && _registry.hasServer(_activeServerId!);

  /// Current server URL.
  String get serverUrl => _activeServerState?.baseUrl ?? '';

  /// Current server ID.
  String? get activeServerId => _activeServerId;

  /// Currently active room ID.
  String? get activeRoomId => _registry.activeRoomId;

  /// Get the active server state, or null if none.
  ServerConnectionState? get _activeServerState => _activeServerId != null
      ? _registry.getServerState(_activeServerId!)
      : null;

  /// Max backgrounded sessions before LRU eviction.
  int get maxBackgroundedSessions => 5;

  void _onRegistryChanged() {
    if (_disposed) return;
    notifyListeners();
  }

  /// Switch to a different server (NON-DESTRUCTIVE).
  ///
  /// serverId optional explicitly provided ID (e.g. from saved state).
  /// If not provided, one is generated from the URL.
  void switchServer(
    String newBaseUrl, {
    Map<String, String>? headers,
    String? serverId,
    EndpointConfiguration? config,
  }) {
    if (_disposed) return;

    // Use provided ID or generate from URL
    final targetServerId = serverId ?? _serverIdFromUrl(newBaseUrl);

    if (_activeServerId == targetServerId) {
      DebugLog.network('ConnectionManager: Server unchanged, skipping switch');
      return;
    }

    DebugLog.network(
      // ignore: lines_longer_than_80_chars (auto-documented)
      'ConnectionManager: Switching server to $newBaseUrl (id: $targetServerId)',
    );

    final serverHeaderRefresher = _headerRefresher != null
        ? () => _headerRefresher(targetServerId)
        : null;

    _registry.connectServer(
      targetServerId,
      newBaseUrl,
      headers: headers,
      headerRefresher: serverHeaderRefresher,
      config: config,
    );
    _activeServerId = targetServerId;
    _registry.focusServer(targetServerId);

    notifyListeners();
  }

  /// Focus a different server by ID.
  void focusServer(String serverId) {
    if (_disposed) return;
    if (!_registry.hasServer(serverId)) {
      throw StateError(
        'Server $serverId not connected. Call switchServer() first.',
      );
    }

    if (_activeServerId == serverId) {
      return;
    }

    DebugLog.network('ConnectionManager: Focusing server $serverId');
    _activeServerId = serverId;
    _registry.focusServer(serverId);
    notifyListeners();
  }

  /// Get list of connected server IDs.
  List<String> get connectedServerIds => _registry.serverIds;

  /// Check if a server is connected.
  bool hasServer(String serverId) => _registry.hasServer(serverId);

  /// Generate a server ID from a URL.
  String _serverIdFromUrl(String url) {
    final uri = Uri.parse(url);
    return '${uri.host}:${uri.port}';
  }

  /// Make an authenticated GET request to the active server.
  Future<http.Response> get(Uri uri) async {
    final serverState = _activeServerState;
    if (serverState == null) {
      throw StateError('No active server configured');
    }
    return serverState.transportLayer.get(uri);
  }

  /// Make an authenticated HEAD request to the active server.
  Future<http.Response> head(Uri uri) async {
    final serverState = _activeServerState;
    if (serverState == null) {
      throw StateError('No active server configured');
    }
    return serverState.transportLayer.head(uri);
  }

  // Getters
  ChatSession? get activeSession {
    final roomId = activeRoomId;
    final serverId = _activeServerId;
    if (roomId == null || serverId == null) return null;
    return _registry.getExistingSession(
      ServerRoomKey(serverId: serverId, roomId: roomId),
    );
  }

  /// Stream of connection events.
  Stream<ConnectionEvent> get events => _eventController.stream;

  /// Get all active connections info.
  List<ConnectionInfo> get activeConnections {
    final serverState = _activeServerState;
    if (serverState == null) return [];
    return serverState.sessions.values.map((s) => s.connectionInfo).toList();
  }

  /// Get connection info for a specific room.
  ConnectionInfo? getConnectionInfo(String roomId) {
    if (_activeServerId == null) return null;
    final session = _registry.getExistingSession(
      ServerRoomKey(serverId: _activeServerId!, roomId: roomId),
    );
    return session?.connectionInfo;
  }

  /// Get or create a session for a room.
  ChatSession getSession(String roomId) {
    if (_activeServerId == null) {
      throw StateError('No server configured. Call switchServer() first.');
    }

    final key = ServerRoomKey(serverId: _activeServerId!, roomId: roomId);
    final session = _registry.getSession(key);
    _subscribeToSession(session);
    return session;
  }

  final Map<String, StreamSubscription<ConnectionEvent>> _sessionSubscriptions =
      {};

  void _subscribeToSession(ChatSession session) {
    if (_disposed) return;

    // We need serverId and roomId for the key.
    // ChatSession interface doesn't guarantee serverId is in connectionInfo?
    // RoomSession has serverId property.
    // connectionInfo has serverId.
    final info = session.connectionInfo;
    final sessionKey = '${info.serverId ?? activeServerId}:${info.roomId}';

    if (_sessionSubscriptions.containsKey(sessionKey)) return;

    _sessionSubscriptions[sessionKey] = session.events.listen((event) {
      if (_disposed) return;
      _eventController.add(event);
      // Clean up subscription if session is disposed
      if (event is SessionDisposedEvent) {
        _sessionSubscriptions.remove(sessionKey)?.cancel();
      }
    });
  }

  /// Get messages for a room.
  List<ChatMessage> getMessages(String roomId) {
    return getSession(roomId).messages;
  }

  /// Get message stream for a room.
  Stream<List<ChatMessage>> getMessageStream(String roomId) {
    return getSession(roomId).messageStream;
  }

  /// Check if agent is typing.
  bool isAgentTyping(String roomId) {
    if (_activeServerId == null) return false;
    final session = _registry.getExistingSession(
      ServerRoomKey(serverId: _activeServerId!, roomId: roomId),
    );
    return session?.isAgentTyping ?? false;
  }

  /// Switch to a different room.
  Future<ChatSession> switchRoom(String newRoomId) async {
    if (_disposed) throw StateError('ConnectionManager is disposed');
    if (_activeServerId == null) {
      throw StateError('No server configured. Call switchServer() first.');
    }

    final key = ServerRoomKey(serverId: _activeServerId!, roomId: newRoomId);
    final previousRoomId = _registry.activeRoomId;

    if (previousRoomId == newRoomId) {
      return getSession(newRoomId);
    }

    DebugLog.network(
      'ConnectionManager: Switching from $previousRoomId to $newRoomId',
    );

    _registry.setActive(key);
    final newSession = getSession(newRoomId);

    _eventController.add(
      RoomSwitchedEvent(
        serverId: _activeServerId,
        roomId: newRoomId,
        previousRoomId: previousRoomId,
      ),
    );

    if (!_disposed) notifyListeners();
    return newSession;
  }

  /// Initialize a session for a room.
  Future<void> initializeSession(String roomId) async {
    if (_disposed) return;
    final serverState = _activeServerState;
    if (serverState == null) {
      throw StateError('No server configured. Call switchServer() first.');
    }

    final session = getSession(roomId);
    if (session is RoomSession) {
      if (session.threadId == null) {
        await session.initialize(transportLayer: serverState.transportLayer);
        if (!_disposed) notifyListeners();
      }
    }
  }

  /// Chat in a room.
  Future<void> chat({
    required String roomId,
    required String userMessage,
    required LocalToolsService localToolsService,
    LocalToolNotifier? onLocalToolExecution,
    @Deprecated('Handled by registry') RoomEventHandler? eventHandler,
    Map<String, dynamic>? state,
  }) async {
    if (_disposed) throw StateError('ConnectionManager is disposed');
    if (!isConfigured) {
      throw StateError(
        'ConnectionManager not configured. Call switchServer() first.',
      );
    }

    final session = getSession(roomId);

    // Legacy handler support
    if (eventHandler != null && session is RoomSession) {
      session.setEventHandler(eventHandler);
    }

    if (session is RoomSession) {
      if (session.threadId == null) {
        await initializeSession(roomId);
      }
      // Note: We ignore tool registration here because RoomSession handles it
      // in initialize.
      // We also ignore 'state' map for now unless we extend ChatSession.
    }

    await session.sendMessage(userMessage, state: state);
  }

  /// Cancel the active run.
  Future<void> cancelRun(String roomId) async {
    if (_disposed) return;
    if (_activeServerId == null) {
      DebugLog.network('ConnectionManager: No server configured');
      return;
    }

    final session = _registry.getExistingSession(
      ServerRoomKey(serverId: _activeServerId!, roomId: roomId),
    );
    if (session == null) {
      DebugLog.network('ConnectionManager: No session for room $roomId');
      return;
    }

    await session.cancel();
    if (!_disposed) notifyListeners();
  }

  /// Clear messages for a room.
  void clearMessages(String roomId) {
    if (_disposed) return;
    if (_activeServerId == null) return;
    final session = _registry.getExistingSession(
      ServerRoomKey(serverId: _activeServerId!, roomId: roomId),
    );
    // Only RoomSession supports manual clear for now
    if (session is RoomSession) {
      session.clearMessages();
    }
    if (!_disposed) notifyListeners();
  }

  /// Load messages for a room.
  void loadMessages(String roomId, List<ChatMessage> messages) {
    if (_disposed) return;
    final session = getSession(roomId);
    if (session is RoomSession) {
      session.loadMessages(messages);
    }
  }

  /// Dispose a specific room session.
  void disposeSession(String roomId) {
    if (_disposed) return;
    final serverState = _activeServerState;
    if (serverState == null) return;

    serverState.disposeSession(roomId);
    if (!_disposed) notifyListeners();
  }

  /// Remove a server and all its sessions.
  void removeServer(String serverId) {
    if (_disposed) return;
    _registry.removeServer(serverId);
    if (_activeServerId == serverId) {
      _activeServerId = null;
    }
    if (!_disposed) notifyListeners();
  }

  /// Dispose all sessions and the manager.
  @override
  void dispose() {
    if (_disposed) return;
    _disposed = true;
    _registry.removeListener(_onRegistryChanged);

    for (final subscription in _sessionSubscriptions.values) {
      subscription.cancel();
    }
    _sessionSubscriptions.clear();

    _eventController.close();
    super.dispose();
  }
}

/// Singleton provider for ConnectionManager.
final connectionManagerProvider = ChangeNotifierProvider<ConnectionManager>((
  ref,
) {
  final registry = ref.read(connectionRegistryProvider);
  final authManager = ref.read(authManagerProvider);

  final manager = ConnectionManager(
    registry: registry,
    headerRefresher: authManager.getAuthHeaders,
  );

  // Listen for lifecycle events and update activity status
  final subscription = manager.events.listen((event) {
    final serverId = event.serverId;
    if (serverId == null) return;

    final key = ServerRoomKey(serverId: serverId, roomId: event.roomId);

    if (event is RunStartedEvent) {
      ref.read(roomActivityStatusProvider(key).notifier).startActivity();
    } else if (event is RunCompletedEvent || event is RunFailedEvent) {
      ref.read(roomActivityStatusProvider(key).notifier).stopActivity();
    } else if (event is RunCancelledEvent) {
      ref.read(roomActivityStatusProvider(key).notifier).stopActivity();
    }
  });

  ref.onDispose(() {
    subscription.cancel();
    manager.dispose();
  });

  return manager;
});
