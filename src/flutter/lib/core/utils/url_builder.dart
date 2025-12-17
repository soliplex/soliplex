import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/providers/app_providers.dart';
import 'package:soliplex/core/utils/api_constants.dart';

/// Centralized URL builder for consistent API endpoint construction.
///
/// baseUrl format: Bare server only (e.g., 'https://server.com').
/// This class handles adding '/api/v1' prefix automatically.
///
/// Example:
/// ```dart
/// final builder = UrlBuilder('https://server.com');
/// builder.rooms();        // https://server.com/api/v1/rooms
/// builder.roomThreads('genui');  // https://server.com/api/v1/rooms/genui/agui
/// ```
class UrlBuilder {
  /// Creates a UrlBuilder with the given base server URL.
  ///
  /// baseUrl should be bare server URL without /api suffix.
  /// Example: 'https://server.com' or 'http://localhost:8000'
  UrlBuilder(String baseUrl) : _baseUrl = normalizeBaseUrl(baseUrl);
  final String _baseUrl;

  /// Get the bare server URL.
  String get serverUrl => _baseUrl;

  /// Get the full API base URL (server + /api/v1).
  String get apiBaseUrl => '$_baseUrl${ApiConstants.apiPath}';

  // =========================================================================
  // ROOMS API
  // =========================================================================

  /// GET /api/v1/rooms - List all rooms.
  Uri rooms() => _apiUri([ApiConstants.rooms]);

  /// GET /api/v1/rooms/{roomId} - Get room details.
  Uri room(String roomId) => _apiUri([ApiConstants.rooms, roomId]);

  /// GET /api/v1/rooms/{roomId}/agui - List threads in room.
  Uri roomThreads(String roomId) =>
      _apiUri([ApiConstants.rooms, roomId, ApiConstants.agui]);

  /// GET /api/v1/rooms/{roomId}/documents - List documents in room.
  Uri roomDocuments(String roomId) =>
      _apiUri([ApiConstants.rooms, roomId, ApiConstants.documents]);

  // =========================================================================
  // AG-UI THREAD API
  // =========================================================================

  /// POST /api/v1/rooms/{roomId}/agui - Create thread.
  Uri createThread(String roomId) =>
      _apiUri([ApiConstants.rooms, roomId, ApiConstants.agui]);

  /// GET /api/v1/rooms/{roomId}/agui/{threadId} - Get thread details.
  Uri thread(String roomId, String threadId) =>
      _apiUri([ApiConstants.rooms, roomId, ApiConstants.agui, threadId]);

  /// POST /api/v1/rooms/{roomId}/agui/{threadId} - Create run.
  Uri createRun(String roomId, String threadId) => thread(roomId, threadId);

  /// POST /api/v1/rooms/{roomId}/agui/{threadId}/meta - Update thread metadata.
  Uri threadMeta(String roomId, String threadId) => _apiUri([
    ApiConstants.rooms,
    roomId,
    ApiConstants.agui,
    threadId,
    ApiConstants.meta,
  ]);

  // =========================================================================
  // AG-UI RUN API
  // =========================================================================

  /// GET /api/v1/rooms/{roomId}/agui/{threadId}/{runId} - Get run details.
  Uri run(String roomId, String threadId, String runId) =>
      _apiUri([ApiConstants.rooms, roomId, ApiConstants.agui, threadId, runId]);

  /// POST /api/v1/rooms/{roomId}/agui/{threadId}/{runId} - Execute run (SSE).
  Uri executeRun(String roomId, String threadId, String runId) =>
      run(roomId, threadId, runId);

  /// Relative endpoint for AG-UI client (without baseUrl, with leading api
  /// path).
  ///
  /// Format: 'api/v1/rooms/{roomId}/agui/{threadId}/{runId}'
  ///
  /// Note: Includes 'api/v1' because the ag_ui client replaces the path
  /// instead of appending to it.
  String runEndpoint(String roomId, String threadId, String runId) =>
      'api/${ApiConstants.apiVersion}/${ApiConstants.rooms}/$roomId/${ApiConstants.agui}/$threadId/$runId';

  /// POST /api/v1/rooms/{roomId}/agui/{threadId}/{runId}/cancel - Cancel run.
  Uri cancelRun(String roomId, String threadId, String runId) => _apiUri([
    ApiConstants.rooms,
    roomId,
    ApiConstants.agui,
    threadId,
    runId,
    ApiConstants.cancel,
  ]);

  /// POST /api/v1/rooms/{roomId}/agui/{threadId}/{runId}/meta - Update run
  /// metadata.
  Uri runMeta(String roomId, String threadId, String runId) => _apiUri([
    ApiConstants.rooms,
    roomId,
    ApiConstants.agui,
    threadId,
    runId,
    ApiConstants.meta,
  ]);

  // =========================================================================
  // MCP API
  // =========================================================================

  /// GET /api/v1/rooms/{roomId}/mcp_token - Get MCP token for room.
  Uri mcpToken(String roomId) =>
      _apiUri([ApiConstants.rooms, roomId, ApiConstants.mcpToken]);

  // =========================================================================
  // AUTH API
  // =========================================================================

  /// GET /api/login - Discover OIDC providers.
  Uri login() => Uri.parse('$_baseUrl/api/${ApiConstants.login}');

  /// GET /api/user_info - Get user info (with auth token).
  Uri userInfo() => Uri.parse('$_baseUrl/api/${ApiConstants.userInfo}');

  // =========================================================================
  // HELPERS
  // =========================================================================

  /// Build a URI with the API path prefix.
  Uri _apiUri(List<String> pathSegments) {
    return Uri.parse(
      '$_baseUrl${ApiConstants.apiPath}/${pathSegments.join('/')}',
    );
  }

  /// Normalize a server URL to bare format.
  ///
  /// - Adds http/https scheme if missing
  /// - Removes trailing slashes
  /// - Strips /api and /api/v1 suffixes
  ///
  /// Example:
  /// ```dart
  /// normalizeBaseUrl('server.com');           // https://server.com
  /// normalizeBaseUrl('localhost:8000');       // http://localhost:8000
  /// normalizeBaseUrl('https://foo.com/api/'); // https://foo.com
  /// ```
  static String normalizeBaseUrl(String url) {
    var normalized = url.trim();

    // Add scheme if missing
    if (!normalized.startsWith('http://') &&
        !normalized.startsWith('https://')) {
      if (normalized.startsWith('localhost') ||
          normalized.startsWith('127.0.0.1')) {
        normalized = 'http://$normalized';
      } else {
        normalized = 'https://$normalized';
      }
    }

    // Remove trailing slashes
    while (normalized.endsWith('/')) {
      normalized = normalized.substring(0, normalized.length - 1);
    }

    // Strip /api and any version suffix (e.g., /api/v1, /api/v2)
    return normalized.replaceAll(RegExp(r'/api(/v\d+)?$'), '');
  }
}

/// Provider for UrlBuilder that uses the current server URL.
///
/// This provider is null when no server is configured.
/// Usage:
/// ```dart
/// final urlBuilder = ref.watch(urlBuilderProvider);
/// if (urlBuilder != null) {
///   final uri = urlBuilder.rooms();
/// }
/// ```
/// Provider for the URL builder based on current server.
///
/// Returns null when no server is configured.
final urlBuilderProvider = Provider<UrlBuilder?>((ref) {
  final server = ref.watch(currentServerFromAppStateProvider);
  if (server == null) return null;
  return UrlBuilder(server.url);
});
