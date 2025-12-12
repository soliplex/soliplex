import 'package:ag_ui/ag_ui.dart' as ag_ui;

import '../utils/debug_log.dart';
import '../utils/url_builder.dart';
import 'connection_events.dart' show SessionState;
import 'http_transport.dart';
import 'room_session.dart';

/// Per-server connection state container.
///
/// Holds all the resources needed to communicate with a single server:
/// - HttpTransport for network operations
/// - ag_ui.AgUiClient for SSE streaming
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

  /// Network transport for this server.
  final HttpTransport transport;

  /// AG-UI client for SSE streaming.
  final ag_ui.AgUiClient agUiClient;

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

  /// Creates a new server connection state.
  ServerConnectionState({
    required this.serverId,
    required this.baseUrl,
    this.headers,
    HttpTransport? transport,
  })  : urlBuilder = UrlBuilder(baseUrl),
        transport = transport ?? HttpTransport(baseUrl: baseUrl, defaultHeaders: headers),
        agUiClient = ag_ui.AgUiClient(
          config: ag_ui.AgUiClientConfig(
            baseUrl: UrlBuilder(baseUrl).serverUrl,
            defaultHeaders: headers ?? {},
          ),
        ),
        lastActivity = DateTime.now() {
    DebugLog.service('ServerConnectionState: Created for server $serverId ($baseUrl)');
  }

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
