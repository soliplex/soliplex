import 'dart:async';
import 'dart:convert';

import 'package:soliplex_client/src/agui/agui_event.dart';
import 'package:soliplex_client/src/agui/text_message_buffer.dart';
import 'package:soliplex_client/src/agui/tool_call_buffer.dart';
import 'package:soliplex_client/src/agui/tool_registry.dart';
import 'package:soliplex_client/src/http/http_transport.dart';
import 'package:soliplex_client/src/models/chat_message.dart';
import 'package:soliplex_client/src/utils/cancel_token.dart';

/// Status of an AG-UI thread run.
enum ThreadRunStatus {
  /// No run is active.
  idle,

  /// A run is currently executing.
  running,

  /// The run finished successfully.
  finished,

  /// The run encountered an error.
  error,
}

/// Manages AG-UI event streaming and state for a conversation thread.
///
/// The Thread class orchestrates SSE (Server-Sent Events) streaming from
/// the backend, parsing events, and updating internal state (messages,
/// tool calls, etc.).
///
/// Example:
/// ```dart
/// final thread = Thread(
///   transport: httpTransport,
///   roomId: 'room-123',
///   threadId: 'thread-456',
/// );
///
/// // Stream events from a run
/// await for (final event in thread.run(
///   runId: 'run-789',
///   userMessage: 'Hello!',
/// )) {
///   print('Event: $event');
/// }
///
/// // Access accumulated messages
/// print('Messages: ${thread.messages}');
/// ```
class Thread {
  /// Creates a thread for the given room and thread IDs.
  Thread({
    required HttpTransport transport,
    required this.roomId,
    required this.threadId,
    ToolRegistry? toolRegistry,
  })  : _transport = transport,
        _toolRegistry = toolRegistry;

  final HttpTransport _transport;
  final ToolRegistry? _toolRegistry;

  /// The room this thread belongs to.
  final String roomId;

  /// The unique identifier for this thread.
  final String threadId;

  // Buffers for streaming content
  final TextMessageBuffer _textBuffer = TextMessageBuffer();
  final ToolCallBuffer _toolCallBuffer = ToolCallBuffer();

  // State
  final List<ChatMessage> _messages = [];
  Map<String, dynamic> _state = {};
  ThreadRunStatus _runStatus = ThreadRunStatus.idle;
  String? _runId;
  String? _errorMessage;

  /// The current run status.
  ThreadRunStatus get runStatus => _runStatus;

  /// The current run ID, if a run is active.
  String? get runId => _runId;

  /// Error message from the last failed run, if any.
  String? get errorMessage => _errorMessage;

  /// All messages accumulated during runs on this thread.
  List<ChatMessage> get messages => List.unmodifiable(_messages);

  /// The current state snapshot.
  Map<String, dynamic> get state => Map.unmodifiable(_state);

  /// Whether a run is currently in progress.
  bool get isRunning => _runStatus == ThreadRunStatus.running;

  /// The text message buffer (for observing streaming state).
  TextMessageBuffer get textBuffer => _textBuffer;

  /// The tool call buffer (for observing tool call state).
  ToolCallBuffer get toolCallBuffer => _toolCallBuffer;

  /// Starts a new run on this thread and streams AG-UI events.
  ///
  /// Parameters:
  /// - [runId]: Unique identifier for this run
  /// - [userMessage]: The user's message to send
  /// - [initialState]: Optional initial state to pass to the backend
  /// - [cancelToken]: Optional token for cancelling the run
  ///
  /// Returns a stream of parsed [AgUiEvent] objects.
  ///
  /// Events are processed internally to update [messages], [state],
  /// and buffer contents. The stream yields each event for observation.
  Stream<AgUiEvent> run({
    required String runId,
    required String userMessage,
    Map<String, dynamic>? initialState,
    CancelToken? cancelToken,
  }) async* {
    // Set run state
    _runId = runId;
    _runStatus = ThreadRunStatus.running;
    _errorMessage = null;

    try {
      // Build the SSE endpoint URI
      final uri = Uri.parse(
        '/api/v1/rooms/$roomId/agui/$threadId/$runId',
      );

      // Prepare request body
      final body = <String, dynamic>{
        'message': userMessage,
        if (initialState != null) 'state': initialState,
      };

      // Start the SSE stream
      final byteStream = _transport.requestStream(
        'POST',
        uri,
        body: body,
        headers: {
          'Accept': 'text/event-stream',
        },
        cancelToken: cancelToken,
      );

      // Parse and yield events
      await for (final event in _parseSSEStream(byteStream)) {
        processEvent(event);
        yield event;

        // Check for run completion
        if (event is RunFinishedEvent) {
          _runStatus = ThreadRunStatus.finished;
        } else if (event is RunErrorEvent) {
          _runStatus = ThreadRunStatus.error;
          _errorMessage = event.message;
        }
      }

      // If stream ended without RUN_FINISHED or RUN_ERROR
      if (_runStatus == ThreadRunStatus.running) {
        _runStatus = ThreadRunStatus.finished;
      }
    } catch (e) {
      _runStatus = ThreadRunStatus.error;
      _errorMessage = e.toString();
      rethrow;
    }
  }

  /// Processes a single AG-UI event and updates internal state.
  ///
  /// This is called automatically during [run], but can also be called
  /// manually for testing or replaying events.
  void processEvent(AgUiEvent event) {
    switch (event) {
      case RunStartedEvent():
        // Run started - no special handling needed
        return;

      case RunFinishedEvent():
        // Complete any pending text message
        _completePendingTextMessage();

      case RunErrorEvent():
        // Complete any pending text message
        _completePendingTextMessage();

      case StepStartedEvent():
      case StepFinishedEvent():
        // Step events - no special handling needed
        return;

      case TextMessageStartEvent(messageId: final messageId):
        _textBuffer.start(messageId: messageId);

      case TextMessageContentEvent(delta: final delta):
        if (_textBuffer.isActive) {
          _textBuffer.append(delta);
        }

      case TextMessageEndEvent():
        if (_textBuffer.isActive) {
          final message = _textBuffer.complete();
          _messages.add(message);
        }

      case ToolCallStartEvent(
          toolCallId: final callId,
          toolCallName: final name,
          parentMessageId: final parentId,
        ):
        _toolCallBuffer.startToolCall(
          callId: callId,
          name: name,
          parentMessageId: parentId,
        );

      case ToolCallArgsEvent(toolCallId: final callId, delta: final delta):
        if (_toolCallBuffer.isActive(callId)) {
          _toolCallBuffer.appendArgs(callId: callId, delta: delta);
        }

      case ToolCallEndEvent(toolCallId: final callId):
        if (_toolCallBuffer.isActive(callId)) {
          final toolCall = _toolCallBuffer.completeToolCall(callId: callId);
          // Execute the tool if registry is available
          _executeToolCall(toolCall);
        }

      case ToolCallResultEvent(
          toolCallId: final callId,
          content: final content,
        ):
        if (_toolCallBuffer.isActive(callId)) {
          _toolCallBuffer.setResult(callId: callId, result: content);
        }

      case StateSnapshotEvent(snapshot: final snapshot):
        _state = _deepCopyMap(snapshot);

      case StateDeltaEvent(delta: final delta):
        _applyJsonPatch(delta);

      case ActivitySnapshotEvent():
      case ActivityDeltaEvent():
        // Activity events - no special handling in basic implementation
        return;

      case MessagesSnapshotEvent(messages: final messagesList):
        // Replace messages with snapshot
        _messages.clear();
        for (final msgJson in messagesList) {
          final message = _parseMessageFromJson(msgJson);
          if (message != null) {
            _messages.add(message);
          }
        }

      case CustomEvent():
      case UnknownEvent():
        // Custom/unknown events - no special handling
        return;
    }
  }

  /// Resets the thread state, clearing messages and buffers.
  void reset() {
    _messages.clear();
    _state = {};
    _textBuffer.reset();
    _toolCallBuffer.reset();
    _runStatus = ThreadRunStatus.idle;
    _runId = null;
    _errorMessage = null;
  }

  /// Parses an SSE byte stream into AG-UI events.
  Stream<AgUiEvent> _parseSSEStream(Stream<List<int>> byteStream) async* {
    final buffer = StringBuffer();

    await for (final chunk in byteStream.transform(utf8.decoder)) {
      buffer.write(chunk);

      // Process complete events (separated by \n\n)
      while (true) {
        final content = buffer.toString();
        final eventEnd = content.indexOf('\n\n');
        if (eventEnd == -1) break;

        final eventText = content.substring(0, eventEnd);
        buffer
          ..clear()
          ..write(content.substring(eventEnd + 2));

        // Parse "data: {...}" line
        final event = _parseSSEEvent(eventText);
        if (event != null) {
          yield event;
        }
      }
    }
  }

  /// Parses a single SSE event text into an AgUiEvent.
  AgUiEvent? _parseSSEEvent(String eventText) {
    // SSE can have multiple lines (event:, data:, id:, etc.)
    // We only care about the data line
    for (final line in eventText.split('\n')) {
      if (line.startsWith('data:')) {
        final jsonString = line.substring(5).trim();
        if (jsonString.isEmpty || jsonString == '[DONE]') {
          continue;
        }
        try {
          final json = jsonDecode(jsonString) as Map<String, dynamic>;
          return AgUiEvent.fromJson(json);
        } catch (_) {
          // Failed to parse JSON - skip this event
        }
      }
    }
    return null;
  }

  /// Completes any pending text message in the buffer.
  void _completePendingTextMessage() {
    if (_textBuffer.isActive) {
      final message = _textBuffer.complete();
      _messages.add(message);
    }
  }

  /// Executes a tool call using the registered tool registry.
  void _executeToolCall(ToolCallInfo toolCall) {
    final registry = _toolRegistry;
    if (registry == null) return;
    if (!registry.isRegistered(toolCall.name)) return;

    // Execute asynchronously
    unawaited(
      registry.execute(toolCall).then((result) {
        if (result != null && _toolCallBuffer.isActive(toolCall.id)) {
          _toolCallBuffer.setResult(callId: toolCall.id, result: result);
        }
      }),
    );
  }

  /// Applies JSON Patch operations to the state.
  void _applyJsonPatch(List<Map<String, dynamic>> operations) {
    for (final op in operations) {
      final operation = op['op'] as String?;
      final path = op['path'] as String?;
      final value = op['value'];

      if (operation == null || path == null) continue;

      // Simple path parsing (handles /key/subkey format)
      final pathParts =
          path.split('/').where((p) => p.isNotEmpty).toList();

      switch (operation) {
        case 'add':
        case 'replace':
          _setAtPath(_state, pathParts, value);
        case 'remove':
          _removeAtPath(_state, pathParts);
        // Note: 'move', 'copy', 'test' are not implemented
        // for simplicity
        default:
          // Ignore unsupported operations
          break;
      }
    }
  }

  /// Sets a value at a path in a nested map.
  void _setAtPath(
    Map<String, dynamic> root,
    List<String> path,
    Object? value,
  ) {
    if (path.isEmpty) return;

    var current = root;
    for (var i = 0; i < path.length - 1; i++) {
      final key = path[i];
      if (current[key] is! Map<String, dynamic>) {
        current[key] = <String, dynamic>{};
      }
      current = current[key] as Map<String, dynamic>;
    }
    current[path.last] = value;
  }

  /// Removes a value at a path in a nested map.
  void _removeAtPath(Map<String, dynamic> root, List<String> path) {
    if (path.isEmpty) return;

    var current = root;
    for (var i = 0; i < path.length - 1; i++) {
      final key = path[i];
      if (current[key] is! Map<String, dynamic>) {
        return; // Path doesn't exist
      }
      current = current[key] as Map<String, dynamic>;
    }
    current.remove(path.last);
  }

  /// Creates a deep copy of a map, recursively copying nested maps.
  Map<String, dynamic> _deepCopyMap(Map<String, dynamic> source) {
    return source.map((key, value) {
      if (value is Map<String, dynamic>) {
        return MapEntry(key, _deepCopyMap(value));
      }
      return MapEntry(key, value);
    });
  }

  /// Parses a ChatMessage from JSON.
  ChatMessage? _parseMessageFromJson(Map<String, dynamic> json) {
    try {
      final id = json['id'] as String? ?? '';
      final text = json['text'] as String?;
      final userStr = json['user'] as String? ?? 'assistant';

      final user = ChatUser.values.firstWhere(
        (u) => u.name == userStr,
        orElse: () => ChatUser.assistant,
      );

      return ChatMessage(
        id: id,
        user: user,
        type: MessageType.text,
        text: text,
        createdAt: DateTime.now(),
      );
    } catch (_) {
      return null;
    }
  }
}
