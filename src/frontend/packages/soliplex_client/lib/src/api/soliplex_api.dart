import 'package:ag_ui/ag_ui.dart' hide CancelToken;
import 'package:soliplex_client/src/api/mappers.dart';
import 'package:soliplex_client/src/application/agui_event_processor.dart';
import 'package:soliplex_client/src/application/streaming_state.dart';
import 'package:soliplex_client/src/domain/chat_message.dart';
import 'package:soliplex_client/src/domain/conversation.dart';
import 'package:soliplex_client/src/domain/room.dart';
import 'package:soliplex_client/src/domain/run_info.dart';
import 'package:soliplex_client/src/domain/thread_info.dart';
import 'package:soliplex_client/src/errors/exceptions.dart';
import 'package:soliplex_client/src/http/http_transport.dart';
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
///   transport: HttpTransport(client: DartHttpClient()),
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
        .map((e) => roomFromJson(e as Map<String, dynamic>))
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
      fromJson: roomFromJson,
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
        .map((e) => threadInfoFromJson(e as Map<String, dynamic>))
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
      fromJson: threadInfoFromJson,
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

    // Extract initial run_id from runs map
    String? initialRunId;
    final runs = response['runs'] as Map<String, dynamic>?;
    if (runs != null && runs.isNotEmpty) {
      initialRunId = runs.keys.first;
    }

    // Normalize response: backend returns thread_id, we use id
    final now = DateTime.now();
    return ThreadInfo(
      id: response['thread_id'] as String,
      roomId: roomId,
      initialRunId: initialRunId ?? '',
      createdAt: now,
      updatedAt: now,
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
      body: <String, dynamic>{},
      cancelToken: cancelToken,
    );

    // Normalize response: backend returns run_id, we use id
    return RunInfo(
      id: response['run_id'] as String,
      threadId: threadId,
      createdAt: DateTime.now(),
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
      fromJson: runInfoFromJson,
    );
  }

  // ============================================================
  // Messages
  // ============================================================

  /// Fetches historical messages for a thread by replaying stored events.
  ///
  /// Parameters:
  /// - [roomId]: The room ID (must not be empty)
  /// - [threadId]: The thread ID (must not be empty)
  ///
  /// Returns a list of [ChatMessage] reconstructed from stored AG-UI events.
  /// Messages are ordered chronologically (oldest first) based on run creation
  /// time.
  ///
  /// This method fetches all runs for a thread, sorts them by creation time,
  /// and replays their events to reconstruct the message history. Use this
  /// when loading a thread that already has conversation history.
  ///
  /// Throws:
  /// - [ArgumentError] if [roomId] or [threadId] is empty
  /// - [NotFoundException] if thread not found (404)
  /// - [AuthException] if not authenticated (401/403)
  /// - [NetworkException] if connection fails
  /// - [ApiException] for other server errors
  /// - [CancelledException] if cancelled via [cancelToken]
  Future<List<ChatMessage>> getThreadMessages(
    String roomId,
    String threadId, {
    CancelToken? cancelToken,
  }) async {
    _requireNonEmpty(roomId, 'roomId');
    _requireNonEmpty(threadId, 'threadId');

    final response = await _transport.request<Map<String, dynamic>>(
      'GET',
      _urlBuilder.build(pathSegments: ['rooms', roomId, 'agui', threadId]),
      cancelToken: cancelToken,
    );

    final runs = response['runs'] as Map<String, dynamic>? ?? {};
    return _extractMessagesFromRuns(runs, threadId);
  }

  /// Extracts messages from runs by replaying events in chronological order.
  List<ChatMessage> _extractMessagesFromRuns(
    Map<String, dynamic> runs,
    String threadId,
  ) {
    if (runs.isEmpty) {
      return [];
    }

    // Sort runs by creation time
    final sortedRuns = _sortRunsByCreationTime(runs);

    // Replay events to reconstruct messages
    var conversation = Conversation.empty(threadId: threadId);
    var streaming = const NotStreaming() as StreamingState;
    const decoder = EventDecoder();
    var skippedEventCount = 0;

    for (final runEntry in sortedRuns) {
      final runData = runEntry.value as Map<String, dynamic>;
      final events = runData['events'] as List<dynamic>? ?? [];

      for (final eventJson in events) {
        try {
          final event = decoder.decodeJson(eventJson as Map<String, dynamic>);
          final result = processEvent(conversation, streaming, event);
          conversation = result.conversation;
          streaming = result.streaming;
        } catch (e) {
          // Skip malformed events - don't fail entire history for one bad
          // event. This can happen if the backend stores events from a newer
          // protocol version or if data corruption occurs.
          skippedEventCount++;
          assert(
            () {
              // ignore: avoid_print
              print('Skipped malformed event during replay: $e');
              return true;
            }(),
            'Debug logging for malformed events',
          );
        }
      }
    }

    if (skippedEventCount > 0) {
      // Log skipped events for observability. Uses print() since
      // soliplex_client is pure Dart without logging dependencies.
      // ignore: avoid_print
      print(
        'Warning: Skipped $skippedEventCount malformed event(s) '
        'while loading thread $threadId',
      );
    }

    return conversation.messages;
  }

  /// Sorts runs by creation time (oldest first).
  List<MapEntry<String, dynamic>> _sortRunsByCreationTime(
    Map<String, dynamic> runs,
  ) {
    return runs.entries.toList()
      ..sort((a, b) {
        final aData = a.value as Map<String, dynamic>;
        final bData = b.value as Map<String, dynamic>;
        final aCreated = aData['created'] as String?;
        final bCreated = bData['created'] as String?;

        if (aCreated == null && bCreated == null) return 0;
        if (aCreated == null) return 1;
        if (bCreated == null) return -1;

        return DateTime.parse(aCreated).compareTo(DateTime.parse(bCreated));
      });
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
