/// Network layer for managing AG-UI connections.
///
/// This module provides:
/// - NetworkTransport - Abstract interface for pluggable networking
/// - HttpTransport - Web-compatible implementation using ag_ui
/// - RoomSession - Per-room state container
/// - ConnectionManager - Central hub for all sessions
/// - NetworkObserver - Read-only visibility into connections
/// - CancelToken - Cancellation support for network operations
library;

export 'cancel_token.dart';
export 'connection_events.dart';
export 'connection_manager.dart';
export 'http_transport.dart';
export 'network_observer.dart';
export 'network_transport.dart';
export 'room_session.dart';
