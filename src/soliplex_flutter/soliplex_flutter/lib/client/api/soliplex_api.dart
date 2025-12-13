import '../models/models.dart';
import '../utils/http_transport.dart';
import '../utils/url_builder.dart';

/// API client for Soliplex backend.
class SoliplexApi {
  SoliplexApi({
    required String baseUrl,
    Map<String, String>? headers,
    HttpTransport? transport,
  }) : _urlBuilder = UrlBuilder(baseUrl),
       _transport =
           transport ??
           HttpTransport(
             baseUrl: UrlBuilder.normalizeBaseUrl(baseUrl),
             defaultHeaders: headers,
           );

  final UrlBuilder _urlBuilder;
  final HttpTransport _transport;

  /// Get URL builder.
  UrlBuilder get urlBuilder => _urlBuilder;

  // === Room endpoints ===

  /// Get all rooms.
  Future<List<Room>> getRooms() async {
    final response = await _transport.get(_urlBuilder.rooms());
    _checkResponse(response);

    // API returns a Map with room IDs as keys
    final map = response.jsonMap;
    return map.values
        .map((e) => Room.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Get a specific room.
  Future<Room> getRoom(String roomId) async {
    final response = await _transport.get(_urlBuilder.room(roomId));
    _checkResponse(response);
    return Room.fromJson(response.jsonMap);
  }

  // === Thread endpoints ===

  /// Get all threads in a room.
  Future<List<ThreadInfo>> getThreads(String roomId) async {
    final response = await _transport.get(_urlBuilder.threads(roomId));
    _checkResponse(response);

    // API returns threads wrapped in {"threads": [...]}
    final map = response.jsonMap;
    final list = map['threads'] as List<dynamic>;
    return list
        .map((e) => ThreadInfo.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Get a specific thread.
  Future<ThreadInfo> getThread(String roomId, String threadId) async {
    final response = await _transport.get(_urlBuilder.thread(roomId, threadId));
    _checkResponse(response);
    return ThreadInfo.fromJson(response.jsonMap);
  }

  /// Create a new thread.
  ///
  /// Returns the created thread info including thread_id and initial run_id.
  Future<Map<String, dynamic>> createThread(String roomId) async {
    // API requires a body (even if empty)
    final response = await _transport.post(
      _urlBuilder.threads(roomId),
      body: {},
    );
    _checkResponse(response);

    final result = Map<String, dynamic>.from(response.jsonMap);

    // Extract run_id from nested runs map (API returns runs as a map)
    final runs = result['runs'] as Map<String, dynamic>?;
    if (runs != null && runs.isNotEmpty) {
      final firstRun = runs.values.first as Map<String, dynamic>;
      result['run_id'] = firstRun['run_id'];
    }

    return result;
  }

  /// Delete a thread.
  Future<void> deleteThread(String roomId, String threadId) async {
    final response = await _transport.delete(
      _urlBuilder.deleteThread(roomId, threadId),
    );
    _checkResponse(response);
  }

  /// Set thread metadata.
  Future<void> setThreadMeta(
    String roomId,
    String threadId, {
    String? name,
    String? description,
  }) async {
    final body = <String, dynamic>{};
    if (name != null) body['name'] = name;
    if (description != null) body['description'] = description;

    final response = await _transport.post(
      _urlBuilder.threadMeta(roomId, threadId),
      body: body,
    );
    _checkResponse(response);
  }

  // === Run endpoints ===

  /// Get a specific run.
  Future<RunInfo> getRun(String roomId, String threadId, String runId) async {
    final response = await _transport.get(
      _urlBuilder.run(roomId, threadId, runId),
    );
    _checkResponse(response);
    return RunInfo.fromJson(response.jsonMap);
  }

  /// Create a new run in a thread.
  Future<Map<String, dynamic>> createRun(String roomId, String threadId) async {
    // API requires a body (even if empty)
    final response = await _transport.post(
      _urlBuilder.createRun(roomId, threadId),
      body: {},
    );
    _checkResponse(response);
    return response.jsonMap;
  }

  /// Set run metadata.
  Future<void> setRunMeta(
    String roomId,
    String threadId,
    String runId, {
    String? label,
  }) async {
    final body = <String, dynamic>{};
    if (label != null) body['label'] = label;

    final response = await _transport.post(
      _urlBuilder.runMeta(roomId, threadId, runId),
      body: body,
    );
    _checkResponse(response);
  }

  void _checkResponse(HttpResponse response) {
    if (!response.isSuccess) {
      throw HttpException(statusCode: response.statusCode, body: response.body);
    }
  }

  /// Close the API client.
  void close() {
    _transport.close();
  }
}
