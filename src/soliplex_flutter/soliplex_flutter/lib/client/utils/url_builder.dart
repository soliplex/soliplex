/// Builds URLs for the Soliplex API.
class UrlBuilder {
  UrlBuilder(String baseUrl) : _baseUrl = normalizeBaseUrl(baseUrl);

  final String _baseUrl;

  /// Normalize a base URL (ensure scheme, strip trailing slash and /api).
  static String normalizeBaseUrl(String url) {
    var normalized = url.trim();

    // Add https:// if no scheme
    if (!normalized.startsWith('http://') &&
        !normalized.startsWith('https://')) {
      normalized = 'https://$normalized';
    }

    // Remove trailing slash
    while (normalized.endsWith('/')) {
      normalized = normalized.substring(0, normalized.length - 1);
    }

    // Remove /api suffix if present
    if (normalized.endsWith('/api')) {
      normalized = normalized.substring(0, normalized.length - 4);
    }

    return normalized;
  }

  /// The server URL (without /api).
  String get serverUrl => _baseUrl;

  /// The API base URL.
  String get apiBaseUrl => '$_baseUrl/api';

  // === Room endpoints ===

  /// GET /api/v1/rooms
  Uri rooms() => Uri.parse('$apiBaseUrl/v1/rooms');

  /// GET /api/v1/rooms/{roomId}
  Uri room(String roomId) => Uri.parse('$apiBaseUrl/v1/rooms/$roomId');

  // === Thread endpoints ===

  /// GET/POST /api/v1/rooms/{roomId}/agui
  Uri threads(String roomId) => Uri.parse('$apiBaseUrl/v1/rooms/$roomId/agui');

  /// GET /api/v1/rooms/{roomId}/agui/{threadId}
  Uri thread(String roomId, String threadId) =>
      Uri.parse('$apiBaseUrl/v1/rooms/$roomId/agui/$threadId');

  /// POST /api/v1/rooms/{roomId}/agui/{threadId}/meta
  Uri threadMeta(String roomId, String threadId) =>
      Uri.parse('$apiBaseUrl/v1/rooms/$roomId/agui/$threadId/meta');

  /// DELETE /api/v1/rooms/{roomId}/agui/{threadId}
  Uri deleteThread(String roomId, String threadId) =>
      Uri.parse('$apiBaseUrl/v1/rooms/$roomId/agui/$threadId');

  // === Run endpoints ===

  /// POST /api/v1/rooms/{roomId}/agui/{threadId} (create run)
  Uri createRun(String roomId, String threadId) =>
      Uri.parse('$apiBaseUrl/v1/rooms/$roomId/agui/$threadId');

  /// GET /api/v1/rooms/{roomId}/agui/{threadId}/{runId}
  Uri run(String roomId, String threadId, String runId) =>
      Uri.parse('$apiBaseUrl/v1/rooms/$roomId/agui/$threadId/$runId');

  /// POST /api/v1/rooms/{roomId}/agui/{threadId}/{runId} (execute run)
  Uri executeRun(String roomId, String threadId, String runId) =>
      Uri.parse('$apiBaseUrl/v1/rooms/$roomId/agui/$threadId/$runId');

  /// POST /api/v1/rooms/{roomId}/agui/{threadId}/{runId}/meta
  Uri runMeta(String roomId, String threadId, String runId) =>
      Uri.parse('$apiBaseUrl/v1/rooms/$roomId/agui/$threadId/$runId/meta');

  /// Endpoint path for AG-UI client (relative path).
  String runEndpointPath(String roomId, String threadId, String runId) =>
      '/api/v1/rooms/$roomId/agui/$threadId/$runId';

  @override
  String toString() => 'UrlBuilder($_baseUrl)';
}
