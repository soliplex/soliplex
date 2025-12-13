import 'dart:async';

import 'package:ag_ui/ag_ui.dart' as ag_ui;

import '../utils/url_builder.dart';
import 'room_session.dart';

/// Events emitted by ConnectionManager.
abstract class ConnectionEvent {}

class SessionCreatedEvent extends ConnectionEvent {
  SessionCreatedEvent(this.roomId, this.threadId);
  final String roomId;
  final String threadId;
}

class SessionDisposedEvent extends ConnectionEvent {
  SessionDisposedEvent(this.roomId, this.threadId);
  final String roomId;
  final String? threadId;
}

class RoomSwitchedEvent extends ConnectionEvent {
  RoomSwitchedEvent(this.roomId, this.previousRoomId);
  final String roomId;
  final String? previousRoomId;
}

/// Manages connections to the Soliplex backend.
///
/// Singleton for app lifetime - NOT server-scoped.
class ConnectionManager {
  ConnectionManager({
    String baseUrl = 'http://localhost:8000',
    Map<String, String>? headers,
  }) {
    _configure(baseUrl, headers);
  }

  late String _baseUrl;
  Map<String, String>? _headers;
  late UrlBuilder _urlBuilder;
  ag_ui.AgUiClient? _agUiClient;

  final Map<String, RoomSession> _sessions = {};
  String? _activeRoomId;

  final StreamController<ConnectionEvent> _eventController =
      StreamController<ConnectionEvent>.broadcast();

  /// Stream of connection events.
  Stream<ConnectionEvent> get events => _eventController.stream;

  /// Current base URL.
  String get baseUrl => _baseUrl;

  /// URL builder.
  UrlBuilder get urlBuilder => _urlBuilder;

  /// Active room ID.
  String? get activeRoomId => _activeRoomId;

  /// AG-UI client.
  ag_ui.AgUiClient? get agUiClient => _agUiClient;

  void _configure(String baseUrl, Map<String, String>? headers) {
    _baseUrl = UrlBuilder.normalizeBaseUrl(baseUrl);
    _headers = headers;
    _urlBuilder = UrlBuilder(_baseUrl);
    _agUiClient = ag_ui.AgUiClient(
      config: ag_ui.AgUiClientConfig(
        baseUrl: _urlBuilder.serverUrl,
        defaultHeaders: _headers ?? {},
      ),
    );
  }

  /// Switch to a different server.
  void switchServer(String newBaseUrl, {Map<String, String>? headers}) {
    final normalizedUrl = UrlBuilder.normalizeBaseUrl(newBaseUrl);
    if (_baseUrl == normalizedUrl && _headersEqual(headers)) {
      return;
    }

    // Dispose all existing sessions
    for (final session in _sessions.values) {
      final threadId = session.threadId;
      session.dispose();
      _eventController.add(SessionDisposedEvent(session.roomId, threadId));
    }
    _sessions.clear();
    _activeRoomId = null;

    _configure(newBaseUrl, headers);
  }

  bool _headersEqual(Map<String, String>? headers) {
    if (_headers == null && headers == null) return true;
    if (_headers == null || headers == null) return false;
    if (_headers!.length != headers.length) return false;
    for (final key in _headers!.keys) {
      if (_headers![key] != headers[key]) return false;
    }
    return true;
  }

  /// Get or create a session for a room.
  RoomSession getSession(String roomId) {
    var session = _sessions[roomId];
    if (session == null) {
      if (_agUiClient == null) {
        throw StateError('ConnectionManager not configured');
      }

      session = RoomSession(
        roomId: roomId,
        baseUrl: _baseUrl,
        agUiClient: _agUiClient!,
      );
      _sessions[roomId] = session;
    }
    return session;
  }

  /// Switch to a different room.
  void switchRoom(String roomId) {
    final previousRoomId = _activeRoomId;

    if (previousRoomId != null && previousRoomId != roomId) {
      _sessions[previousRoomId]?.suspend();
    }

    _activeRoomId = roomId;
    final session = getSession(roomId);
    session.resume();

    _eventController.add(RoomSwitchedEvent(roomId, previousRoomId));
  }

  /// Initialize a session with a thread ID.
  void initializeSession(String roomId, String threadId) {
    final session = getSession(roomId);
    session.initializeThread(threadId);
    _eventController.add(SessionCreatedEvent(roomId, threadId));
  }

  /// Get messages for a room.
  List<dynamic> getMessages(String roomId) {
    return _sessions[roomId]?.messages ?? [];
  }

  /// Get message stream for a room.
  Stream<List<dynamic>>? getMessageStream(String roomId) {
    return _sessions[roomId]?.messageStream;
  }

  /// Cancel the current run for a room.
  void cancelRun(String roomId) {
    _sessions[roomId]?.cancel();
  }

  /// Dispose a specific session.
  void disposeSession(String roomId) {
    final session = _sessions.remove(roomId);
    if (session != null) {
      final threadId = session.threadId;
      session.dispose();
      _eventController.add(SessionDisposedEvent(roomId, threadId));
    }
  }

  /// Dispose all resources.
  void dispose() {
    for (final session in _sessions.values) {
      session.dispose();
    }
    _sessions.clear();
    _eventController.close();
  }

  @override
  String toString() =>
      'ConnectionManager(baseUrl: $_baseUrl, sessions: ${_sessions.length})';
}
