/// Soliplex Client - Pure Dart client for Soliplex backend.
///
/// This library provides a complete client implementation for interacting
/// with the Soliplex backend through HTTP and AG-UI protocols.
///
/// Usage:
/// ```dart
/// import 'package:soliplex_flutter/client/client.dart';
///
/// final client = SoliplexClient(baseUrl: 'http://localhost:8000');
/// final rooms = await client.getRooms();
/// ```
library;

// Main client
export 'soliplex_client.dart';

// Models
export 'models/models.dart';

// API
export 'api/api.dart';

// Session management
export 'session/session.dart';

// AG-UI protocol
export 'agui/agui.dart';

// Utilities
export 'utils/utils.dart';
