import 'package:ag_ui/ag_ui.dart' as ag_ui;

import '../utils/debug_log.dart';
import '../utils/url_builder.dart';
import 'connection_events.dart' show SessionState;
import 'http_transport.dart';
import 'network_inspector.dart';
import 'network_transport_layer.dart';
import 'room_session.dart';

/// Per-server connection state container.
///
/// Holds all the resources needed to communicate with a single server:
/// - NetworkTransportLayer for unified HTTP/SSE transport
/// - HttpTransport for API operations
/// - Map of room sessions
///
/// Created and managed by [ConnectionRegistry].
class ServerConnectionState {
  /// Unique identifier for this server connection.
  final String serverId;

  /// Base URL of the server.
  final String baseUrl;

  /// Auth headers for this server.
  final Map<String, String>? headers;

  /// Unified transport layer owning http.Client and AgUiClient.
  final NetworkTransportLayer _transportLayer;

  /// Network transport for API operations.
  final HttpTransport transport;

  /// URL builder for this server.
  final UrlBuilder urlBuilder;

  /// Room sessions for this server.
  final Map<String, RoomSession> sessions = {};

  /// Last activity timestamp for timeout tracking.
  DateTime lastActivity;

  /// Currently active room ID for this server.
  String? activeRoomId;

  /// Whether this server connection has been disposed.
  bool _disposed = false;

  /// Private constructor used by factory.
  ServerConnectionState._({
    required this.serverId,
    required this.baseUrl,
    required this.headers,
    required NetworkTransportLayer transportLayer,
    required this.transport,
  })  : urlBuilder = UrlBuilder(baseUrl),
        _transportLayer = transportLayer,
        lastActivity = DateTime.now() {
    DebugLog.service('ServerConnectionState: Created for server $serverId ($baseUrl)');
  }

  /// Creates a new server connection state.
  ///
  /// [headerRefresher] is called on 401 to refresh auth headers.
  /// [inspector] is optional network inspector for traffic capture.
  factory ServerConnectionState({
    required String serverId,
    required String baseUrl,
    Map<String, String>? headers,
    HttpTransport? transport,
    NetworkTransportLayer? transportLayer,
    Future<Map<String, String>> Function()? headerRefresher,
    NetworkInspector? inspector,
  }) {
    // Create or use provided transport layer
    final layer = transportLayer ?? NetworkTransportLayer(
      baseUrl: baseUrl,
      defaultHeaders: headers,
      headerRefresher: headerRefresher,
      inspector: inspector,
    );

    // Create or use provided HttpTransport
    final httpTransport = transport ?? HttpTransport.fromTransportLayer(
      baseUrl: baseUrl,
      transportLayer: layer,
    );

    return ServerConnectionState._(
      serverId: serverId,
      baseUrl: baseUrl,
      headers: headers,
      transportLayer: layer,
      transport: httpTransport,
    );
  }

  /// The unified transport layer for HTTP and SSE.
  ///
  /// Use this for SSE streaming to enable NetworkInspector observability.
  NetworkTransportLayer get transportLayer => _transportLayer;

  /// AG-UI client for SSE streaming.
  ///
  /// Obtained from the transport layer for unified network management.
  /// Prefer using [transportLayer] directly for new code.
  ag_ui.AgUiClient get agUiClient => _transportLayer.agUiClient;

  /// Whether this state has been disposed.
  bool get isDisposed => _disposed;

  /// Number of active sessions.
  int get sessionCount => sessions.length;

  /// Number of backgrounded sessions.
  int get backgroundedSessionCount =>
      sessions.values.where((s) => s.state == SessionState.backgrounded).length;

  /// Updates the last activity timestamp.
  void touch() {
    lastActivity = DateTime.now();
  }

  /// Gets or creates a session for the given room.
  ///
  /// Returns an existing session if one exists, otherwise creates a new one.
  RoomSession getOrCreateSession(String roomId) {
    if (_disposed) {
      throw StateError('Cannot get session from disposed ServerConnectionState');
    }

    touch();

    var session = sessions[roomId];
    if (session != null) {
      return session;
    }

    session = RoomSession(
      roomId: roomId,
      serverId: serverId,
      baseUrl: baseUrl,
      transport: transport,
    );
    sessions[roomId] = session;

    DebugLog.service('ServerConnectionState: Created session for room $roomId');
    return session;
  }

  /// Gets an existing session, or null if not found.
  RoomSession? getSession(String roomId) {
    touch();
    return sessions[roomId];
  }

  /// Removes and disposes a session.
  void disposeSession(String roomId) {
    final session = sessions.remove(roomId);
    if (session != null) {
      session.dispose();
      DebugLog.service('ServerConnectionState: Disposed session for room $roomId');
    }

    if (activeRoomId == roomId) {
      activeRoomId = null;
    }
  }

  /// Gets backgrounded sessions sorted by last activity (oldest first).
  List<RoomSession> getBackgroundedSessionsByAge() {
    final backgrounded = sessions.values
        .where((s) => s.state == SessionState.backgrounded)
        .toList();
    backgrounded.sort((a, b) {
      final aTime = a.lastActivity ?? DateTime(1970);
      final bTime = b.lastActivity ?? DateTime(1970);
      return aTime.compareTo(bTime);
    });
    return backgrounded;
  }

  /// Evicts the oldest backgrounded sessions to stay within the limit.
  ///
  /// Returns the number of sessions evicted.
  int evictOldestBackgroundedSessions(int maxBackgrounded) {
    var evicted = 0;
    while (backgroundedSessionCount > maxBackgrounded) {
      final oldest = getBackgroundedSessionsByAge().firstOrNull;
      if (oldest == null) break;
      disposeSession(oldest.roomId);
      evicted++;
    }
    return evicted;
  }

  /// Disposes all sessions and resources.
  void dispose() {
    if (_disposed) return;
    _disposed = true;

    DebugLog.service('ServerConnectionState: Disposing server $serverId');

    for (final session in sessions.values) {
      session.dispose();
    }
    sessions.clear();

    transport.close();
    _transportLayer.close();
  }

  @override
  String toString() {
    return 'ServerConnectionState('
        'serverId: $serverId, '
        'baseUrl: $baseUrl, '
        'sessions: ${sessions.length}, '
        'active: $activeRoomId)';
  }
}
