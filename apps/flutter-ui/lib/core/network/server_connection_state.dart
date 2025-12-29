import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:soliplex/core/models/endpoint_models.dart';
import 'package:soliplex/core/network/connection_events.dart' show SessionState;
import 'package:soliplex/core/network/http_transport.dart';
import 'package:soliplex/core/network/network_inspector.dart';
import 'package:soliplex/core/network/network_transport_layer.dart';
import 'package:soliplex/core/network/room_session.dart';
import 'package:soliplex/core/protocol/chat_session.dart';
import 'package:soliplex/core/protocol/completions_chat_session.dart';
import 'package:soliplex/core/protocol/completions_client.dart';
import 'package:soliplex/core/services/local_tools_service.dart';
import 'package:soliplex/core/state/app_state.dart';
import 'package:soliplex/core/utils/debug_log.dart';
import 'package:soliplex/core/utils/url_builder.dart';

/// Per-server connection state container.
///
/// Holds all the resources needed to communicate with a single server:
/// - NetworkTransportLayer for unified HTTP/SSE transport
/// - HttpTransport for API operations
/// - Map of room sessions
///
/// Created and managed by ConnectionRegistry.
class ServerConnectionState {
  /// Creates a new server connection state.
  factory ServerConnectionState({
    required String serverId,
    required String baseUrl,
    Map<String, String>? headers,
    HttpTransport? transport,
    NetworkTransportLayer? transportLayer,
    Future<Map<String, String>> Function()? headerRefresher,
    NetworkInspector? inspector,
    LocalToolsService? localToolsService,
    EndpointConfiguration? config,
    Stream<AppState>? appStateStream,
  }) {
    // Create or use provided transport layer
    final layer =
        transportLayer ??
        NetworkTransportLayer(
          baseUrl: baseUrl,
          defaultHeaders: headers,
          headerRefresher: headerRefresher,
          inspector: inspector,
        );

    // Create or use provided HttpTransport
    final httpTransport =
        transport ??
        HttpTransport.fromTransportLayer(
          baseUrl: baseUrl,
          transportLayer: layer,
        );

    return ServerConnectionState._(
      serverId: serverId,
      baseUrl: baseUrl,
      headers: headers,
      transportLayer: layer,
      transport: httpTransport,
      localToolsService: localToolsService,
      config: config,
      appStateStream: appStateStream,
    );
  }

  /// Private constructor used by factory.
  ServerConnectionState._({
    required this.serverId,
    required this.baseUrl,
    required this.headers,
    required NetworkTransportLayer transportLayer,
    required this.transport,
    this.localToolsService,
    this.config,
    this.appStateStream,
  }) : urlBuilder = UrlBuilder(baseUrl),
       _transportLayer = transportLayer,
       lastActivity = DateTime.now() {
    DebugLog.service(
      'ServerConnectionState: Created for server $serverId ($baseUrl)',
    );
  }

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

  /// Local tools service for the session.
  final LocalToolsService? localToolsService;

  /// Endpoint configuration (defines type and settings).
  final EndpointConfiguration? config;

  /// Stream of app state changes (for auth awareness).
  final Stream<AppState>? appStateStream;

  /// Room sessions for this server (polymorphic).
  final Map<String, ChatSession> sessions = {};

  /// Last activity timestamp for timeout tracking.
  DateTime lastActivity;

  /// Currently active room ID for this server.
  String? activeRoomId;

  /// Whether this server connection has been disposed.
  bool _disposed = false;

  /// The unified transport layer for HTTP and SSE.
  ///
  /// Use this for SSE streaming to enable NetworkInspector observability.
  NetworkTransportLayer get transportLayer => _transportLayer;

  /// AG-UI client for SSE streaming.
  ag_ui.AgUiClient get agUiClient => _transportLayer.agUiClient;

  /// Whether this state has been disposed.
  bool get isDisposed => _disposed;

  /// Number of active sessions.
  int get sessionCount => sessions.length;

  /// Number of backgrounded sessions.
  int get backgroundedSessionCount => sessions.values.where((s) {
    if (s is RoomSession) return s.state == SessionState.backgrounded;
    return false; // Other session types don't support backgrounding logic yet
  }).length;

  /// Updates the last activity timestamp.
  void touch() {
    lastActivity = DateTime.now();
  }

  /// Gets or creates a session for the given room.
  ///
  /// Returns an existing session if one exists, otherwise creates a new one.
  ChatSession getOrCreateSession(String roomId) {
    if (_disposed) {
      throw StateError(
        'Cannot get session from disposed ServerConnectionState',
      );
    }

    touch();

    var session = sessions[roomId];
    if (session != null) {
      return session;
    }

    if (config is CompletionsEndpoint) {
      final compConfig = config! as CompletionsEndpoint;
      // Extract API key from headers (injected by SessionLifecycleController)
      final apiKey =
          headers?['Authorization']?.replaceFirst('Bearer ', '') ?? '';

      session = CompletionsChatSession(
        model: compConfig.model,
        client: CompletionsClient(
          baseUrl: baseUrl,
          apiKey: apiKey,
          transportLayer: _transportLayer, // Pass the transport layer
        ),
      );
      DebugLog.service(
        'ServerConnectionState: Created completions session for room $roomId',
      );
    } else {
      // Default to AG-UI RoomSession
      session = RoomSession(
        roomId: roomId,
        serverId: serverId,
        baseUrl: baseUrl,
        transport: transport,
        localToolsService: localToolsService,
        appStateStream: appStateStream,
      );
      DebugLog.service(
        'ServerConnectionState: Created RoomSession for room $roomId',
      );
    }

    sessions[roomId] = session;
    return session;
  }

  /// Gets an existing session, or null if not found.
  ChatSession? getSession(String roomId) {
    touch();
    return sessions[roomId];
  }

  /// Removes and disposes a session.
  void disposeSession(String roomId) {
    final session = sessions.remove(roomId);
    if (session != null) {
      session.dispose();
      DebugLog.service(
        'ServerConnectionState: Disposed session for room $roomId',
      );
    }

    if (activeRoomId == roomId) {
      activeRoomId = null;
    }
  }

  /// Gets backgrounded sessions sorted by last activity (oldest first).
  List<RoomSession> getBackgroundedSessionsByAge() {
    final backgrounded = sessions.values
        .whereType<RoomSession>()
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
