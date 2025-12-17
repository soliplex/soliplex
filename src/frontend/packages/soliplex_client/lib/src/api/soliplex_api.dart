import 'package:soliplex_client/src/errors/exceptions.dart';
import 'package:soliplex_client/src/http/http_transport.dart';
import 'package:soliplex_client/src/models/room.dart';
import 'package:soliplex_client/src/models/run_info.dart';
import 'package:soliplex_client/src/models/thread_info.dart';
import 'package:soliplex_client/src/utils/cancel_token.dart';
import 'package:soliplex_client/src/utils/url_builder.dart';

/// API client for Soliplex backend CRUD operations.
///
/// Provides methods for managing rooms, threads, and runs.
/// Built on top of [HttpTransport] for JSON handling and error mapping.
///
/// Example:
/// ```dart
/// final api = SoliplexApi(
///   transport: HttpTransport(adapter: DartHttpAdapter()),
///   urlBuilder: UrlBuilder('https://api.example.com/api/v1'),
/// );
///
/// // List rooms
/// final rooms = await api.getRooms();
///
/// // Create a thread
/// final thread = await api.createThread('room-123');
/// print('Created thread: ${thread.id}');
///
/// api.close();
/// ```
class SoliplexApi {
  /// Creates an API client with the given [transport] and [urlBuilder].
  ///
  /// Parameters:
  /// - [transport]: HTTP transport for making requests
  /// - [urlBuilder]: URL builder configured with the API base URL
  SoliplexApi({
    required HttpTransport transport,
    required UrlBuilder urlBuilder,
  })  : _transport = transport,
        _urlBuilder = urlBuilder;

  final HttpTransport _transport;
  final UrlBuilder _urlBuilder;

  // ============================================================
  // Rooms
  // ============================================================

  /// Lists all available rooms.
  ///
  /// Returns a list of [Room] objects.
  ///
  /// The backend returns rooms as a map keyed by room ID. This method
  /// converts the map to a list of Room objects.
  ///
  /// Throws:
  /// - [AuthException] if not authenticated (401/403)
  /// - [NetworkException] if connection fails
  /// - [ApiException] for other server errors
  /// - [CancelledException] if cancelled via [cancelToken]
  Future<List<Room>> getRooms({CancelToken? cancelToken}) async {
    final response = await _transport.request<Map<String, dynamic>>(
      'GET',
      _urlBuilder.build(path: 'rooms'),
      cancelToken: cancelToken,
    );
    // Backend returns a map of room_id -> room object
    // Convert to list of Room objects
    return response.values
        .map((e) => Room.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Gets a room by ID.
  ///
  /// Parameters:
  /// - [roomId]: The room ID (must not be empty)
  ///
  /// Returns the [Room] with the given ID.
  ///
  /// Throws:
  /// - [ArgumentError] if [roomId] is empty
  /// - [NotFoundException] if room not found (404)
  /// - [AuthException] if not authenticated (401/403)
  /// - [NetworkException] if connection fails
  /// - [ApiException] for other server errors
  /// - [CancelledException] if cancelled via [cancelToken]
  Future<Room> getRoom(String roomId, {CancelToken? cancelToken}) async {
    _requireNonEmpty(roomId, 'roomId');

    return _transport.request<Room>(
      'GET',
      _urlBuilder.build(pathSegments: ['rooms', roomId]),
      cancelToken: cancelToken,
      fromJson: Room.fromJson,
    );
  }

  // ============================================================
  // Threads
  // ============================================================

  /// Lists all threads in a room.
  ///
  /// Parameters:
  /// - [roomId]: The room ID (must not be empty)
  ///
  /// Returns a list of [ThreadInfo] objects for the room.
  ///
  /// The backend returns threads wrapped in a {"threads": [...]} object.
  /// This method extracts the threads array.
  ///
  /// Throws:
  /// - [ArgumentError] if [roomId] is empty
  /// - [NotFoundException] if room not found (404)
  /// - [AuthException] if not authenticated (401/403)
  /// - [NetworkException] if connection fails
  /// - [ApiException] for other server errors
  /// - [CancelledException] if cancelled via [cancelToken]
  Future<List<ThreadInfo>> getThreads(
    String roomId, {
    CancelToken? cancelToken,
  }) async {
    _requireNonEmpty(roomId, 'roomId');

    final response = await _transport.request<Map<String, dynamic>>(
      'GET',
      _urlBuilder.build(pathSegments: ['rooms', roomId, 'agui']),
      cancelToken: cancelToken,
    );
    // Backend returns {"threads": [...]} - extract the threads array
    final threads = response['threads'] as List<dynamic>;
    return threads
        .map((e) => ThreadInfo.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Gets a thread by ID.
  ///
  /// Parameters:
  /// - [roomId]: The room ID (must not be empty)
  /// - [threadId]: The thread ID (must not be empty)
  ///
  /// Returns the [ThreadInfo] with the given ID.
  ///
  /// Throws:
  /// - [ArgumentError] if [roomId] or [threadId] is empty
  /// - [NotFoundException] if thread not found (404)
  /// - [AuthException] if not authenticated (401/403)
  /// - [NetworkException] if connection fails
  /// - [ApiException] for other server errors
  /// - [CancelledException] if cancelled via [cancelToken]
  Future<ThreadInfo> getThread(
    String roomId,
    String threadId, {
    CancelToken? cancelToken,
  }) async {
    _requireNonEmpty(roomId, 'roomId');
    _requireNonEmpty(threadId, 'threadId');

    return _transport.request<ThreadInfo>(
      'GET',
      _urlBuilder.build(pathSegments: ['rooms', roomId, 'agui', threadId]),
      cancelToken: cancelToken,
      fromJson: ThreadInfo.fromJson,
    );
  }

  /// Creates a new thread in a room.
  ///
  /// Parameters:
  /// - [roomId]: The room ID (must not be empty)
  ///
  /// Returns a [ThreadInfo] for the newly created thread.
  ///
  /// Throws:
  /// - [ArgumentError] if [roomId] is empty
  /// - [NotFoundException] if room not found (404)
  /// - [AuthException] if not authenticated (401/403)
  /// - [NetworkException] if connection fails
  /// - [ApiException] for other server errors
  /// - [CancelledException] if cancelled via [cancelToken]
  Future<ThreadInfo> createThread(
    String roomId, {
    CancelToken? cancelToken,
  }) async {
    _requireNonEmpty(roomId, 'roomId');

    final response = await _transport.request<Map<String, dynamic>>(
      'POST',
      _urlBuilder.build(pathSegments: ['rooms', roomId, 'agui']),
      body: const {
        'metadata': {
          'name': 'New Thread',
          'description': '',
        },
      },
      cancelToken: cancelToken,
    );

    // Normalize response: backend returns thread_id, we use id
    return ThreadInfo(
      id: response['thread_id'] as String,
      roomId: roomId,
    );
  }

  /// Deletes a thread.
  ///
  /// Parameters:
  /// - [roomId]: The room ID (must not be empty)
  /// - [threadId]: The thread ID (must not be empty)
  ///
  /// Throws:
  /// - [ArgumentError] if [roomId] or [threadId] is empty
  /// - [NotFoundException] if thread not found (404)
  /// - [AuthException] if not authenticated (401/403)
  /// - [NetworkException] if connection fails
  /// - [ApiException] for other server errors
  /// - [CancelledException] if cancelled via [cancelToken]
  Future<void> deleteThread(
    String roomId,
    String threadId, {
    CancelToken? cancelToken,
  }) async {
    _requireNonEmpty(roomId, 'roomId');
    _requireNonEmpty(threadId, 'threadId');

    await _transport.request<void>(
      'DELETE',
      _urlBuilder.build(pathSegments: ['rooms', roomId, 'agui', threadId]),
      cancelToken: cancelToken,
    );
  }

  // ============================================================
  // Runs
  // ============================================================

  /// Creates a new run in a thread.
  ///
  /// Parameters:
  /// - [roomId]: The room ID (must not be empty)
  /// - [threadId]: The thread ID (must not be empty)
  ///
  /// Returns a [RunInfo] for the newly created run.
  ///
  /// Throws:
  /// - [ArgumentError] if [roomId] or [threadId] is empty
  /// - [NotFoundException] if thread not found (404)
  /// - [AuthException] if not authenticated (401/403)
  /// - [NetworkException] if connection fails
  /// - [ApiException] for other server errors
  /// - [CancelledException] if cancelled via [cancelToken]
  Future<RunInfo> createRun(
    String roomId,
    String threadId, {
    CancelToken? cancelToken,
  }) async {
    _requireNonEmpty(roomId, 'roomId');
    _requireNonEmpty(threadId, 'threadId');

    final response = await _transport.request<Map<String, dynamic>>(
      'POST',
      _urlBuilder.build(pathSegments: ['rooms', roomId, 'agui', threadId]),
      cancelToken: cancelToken,
    );

    // Normalize response: backend returns run_id, we use id
    return RunInfo(
      id: response['run_id'] as String,
      threadId: threadId,
    );
  }

  /// Gets a run by ID.
  ///
  /// Parameters:
  /// - [roomId]: The room ID (must not be empty)
  /// - [threadId]: The thread ID (must not be empty)
  /// - [runId]: The run ID (must not be empty)
  ///
  /// Returns the [RunInfo] with the given ID.
  ///
  /// Throws:
  /// - [ArgumentError] if any ID is empty
  /// - [NotFoundException] if run not found (404)
  /// - [AuthException] if not authenticated (401/403)
  /// - [NetworkException] if connection fails
  /// - [ApiException] for other server errors
  /// - [CancelledException] if cancelled via [cancelToken]
  Future<RunInfo> getRun(
    String roomId,
    String threadId,
    String runId, {
    CancelToken? cancelToken,
  }) async {
    _requireNonEmpty(roomId, 'roomId');
    _requireNonEmpty(threadId, 'threadId');
    _requireNonEmpty(runId, 'runId');

    return _transport.request<RunInfo>(
      'GET',
      _urlBuilder.build(
        pathSegments: ['rooms', roomId, 'agui', threadId, runId],
      ),
      cancelToken: cancelToken,
      fromJson: RunInfo.fromJson,
    );
  }

  // ============================================================
  // Lifecycle
  // ============================================================

  /// Closes the API client and releases resources.
  ///
  /// After calling this method, no further requests should be made.
  void close() {
    _transport.close();
  }

  // ============================================================
  // Private helpers
  // ============================================================

  /// Validates that a string value is not empty.
  void _requireNonEmpty(String value, String name) {
    if (value.isEmpty) {
      throw ArgumentError.value(value, name, 'must not be empty');
    }
  }
}
