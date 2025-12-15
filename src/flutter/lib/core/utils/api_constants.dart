/// API constants and default configurations.
///
/// Centralizes all API-related constants to ensure consistency
/// across the codebase.
class ApiConstants {
  ApiConstants._();

  /// Default server URL (bare server, no /api prefix).
  static const String defaultServerUrl = 'http://localhost:8000';

  /// API version string.
  static const String apiVersion = 'v1';

  /// Full API path segment (e.g., '/api/v1').
  static const String apiPath = '/api/$apiVersion';

  // === Path Segments ===

  /// Rooms path segment.
  static const String rooms = 'rooms';

  /// AG-UI path segment (for streaming endpoints).
  static const String agui = 'agui';

  /// Login path segment.
  static const String login = 'login';

  /// User info path segment.
  static const String userInfo = 'user_info';

  /// Metadata path segment.
  static const String meta = 'meta';

  /// Cancel path segment.
  static const String cancel = 'cancel';

  /// MCP token path segment.
  static const String mcpToken = 'mcp_token';

  /// Documents path segment.
  static const String documents = 'documents';
}
