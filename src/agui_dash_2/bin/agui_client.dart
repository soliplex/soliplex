// Standalone Dart CLI client for testing AG-UI 3-step flow
// Run with: dart run bin/agui_client.dart
//
// This client tests the AG-UI flow:
// 1. POST /api/v1/rooms/{room_id}/agui -> creates thread WITH initial run
// 2. POST /api/v1/rooms/{room_id}/agui/{thread_id}/{run_id} -> SSE stream

import 'dart:async';
import 'dart:convert';
import 'dart:io';

const String baseUrl = 'http://localhost:8000/api/v1';
const String roomId = 'joker';
const String testMessage = 'tell me a computer joke';

Future<void> main() async {
  print('=== AG-UI CLI Client Test ===\n');
  print('Base URL: $baseUrl');
  print('Room ID: $roomId');
  print('Message: "$testMessage"\n');

  final client = HttpClient();

  try {
    // Step 1: Create Thread (which also creates initial run)
    print('Step 1: Creating thread (with initial run)...');
    final (threadId, runId) = await createThread(client);
    print('  Thread ID: $threadId');
    print('  Run ID: $runId\n');

    // Step 2: Execute Run with SSE streaming
    print('Step 2: Sending message and streaming response...');
    print('-' * 50);
    await executeRun(client, threadId, runId, testMessage);
    print('-' * 50);

    print('\nTest completed successfully!');
  } catch (e, stack) {
    print('\nError: $e');
    print('Stack trace:\n$stack');
    exit(1);
  } finally {
    client.close();
  }
}

/// Step 1: Create a new thread (server auto-creates initial run)
/// Returns (threadId, runId)
Future<(String, String)> createThread(HttpClient client) async {
  final uri = Uri.parse('$baseUrl/rooms/$roomId/agui');
  final request = await client.postUrl(uri);
  request.headers.contentType = ContentType.json;
  // AGUI_NewThreadRequest - just optional metadata
  request.write('{}');

  final response = await request.close();
  final body = await response.transform(utf8.decoder).join();

  if (response.statusCode != 200) {
    throw Exception('Failed to create thread: ${response.statusCode} $body');
  }

  final data = jsonDecode(body) as Map<String, dynamic>;

  // Response is AGUI_Thread with:
  // - thread_id: string
  // - runs: {run_id: AGUI_Run, ...}
  final threadId = data['thread_id'] as String?;
  if (threadId == null) {
    throw Exception('Server did not return thread_id. Response: $body');
  }

  // Get the run_id from the runs map
  final runs = data['runs'] as Map<String, dynamic>?;
  if (runs == null || runs.isEmpty) {
    throw Exception('Server did not return any runs. Response: $body');
  }

  // Get the first (and only) run_id
  final runId = runs.keys.first;

  return (threadId, runId);
}

/// Step 2: Execute the run and stream SSE events
Future<void> executeRun(
  HttpClient client,
  String threadId,
  String runId,
  String message,
) async {
  final uri = Uri.parse('$baseUrl/rooms/$roomId/agui/$threadId/$runId');
  final request = await client.postUrl(uri);
  request.headers.contentType = ContentType.json;
  request.headers.add('Accept', 'text/event-stream');

  // Build AG-UI RunAgentInput payload
  // IMPORTANT: thread_id and run_id must match what the server knows
  final input = {
    'thread_id': threadId,
    'run_id': runId,
    'messages': [
      {
        'role': 'user',
        'id': DateTime.now().millisecondsSinceEpoch.toString(),
        'content': message,
      },
    ],
    'tools': [],
    'context': [],
    'state': {},
    'forwardedProps': {},
  };

  print('Sending payload:');
  print(const JsonEncoder.withIndent('  ').convert(input));
  print('');

  request.write(jsonEncode(input));

  final response = await request.close();

  if (response.statusCode != 200) {
    final body = await response.transform(utf8.decoder).join();
    throw Exception('SSE request failed: ${response.statusCode} $body');
  }

  // Parse SSE stream
  final buffer = StringBuffer();
  final responseText = StringBuffer();

  await for (final chunk in response.transform(utf8.decoder)) {
    buffer.write(chunk);

    // Process complete SSE messages (separated by double newlines)
    var content = buffer.toString();
    while (content.contains('\n\n')) {
      final endIndex = content.indexOf('\n\n');
      final sseMessage = content.substring(0, endIndex);
      content = content.substring(endIndex + 2);
      buffer.clear();
      buffer.write(content);

      // Parse and display the SSE event
      final event = parseSseMessage(sseMessage);
      if (event != null) {
        displayEvent(event, responseText);
      }
    }
  }

  // Handle any remaining content
  if (buffer.isNotEmpty) {
    final event = parseSseMessage(buffer.toString());
    if (event != null) {
      displayEvent(event, responseText);
    }
  }

  print('\n');
  print('=== FULL RESPONSE ===');
  print(responseText.toString());
}

/// Parse a single SSE message
Map<String, dynamic>? parseSseMessage(String message) {
  String? eventType;
  String? data;

  for (final line in message.split('\n')) {
    if (line.startsWith('event:')) {
      eventType = line.substring(6).trim();
    } else if (line.startsWith('data:')) {
      data = line.substring(5).trim();
    }
  }

  if (data == null || data.isEmpty) {
    return null;
  }

  try {
    final json = jsonDecode(data) as Map<String, dynamic>;
    // Add event type if extracted from SSE header
    if (eventType != null && !json.containsKey('type')) {
      json['type'] = eventType;
    }
    return json;
  } catch (e) {
    print('  [PARSE ERROR] $e');
    print('  Raw data: $data');
    return null;
  }
}

/// Display an SSE event nicely
void displayEvent(Map<String, dynamic> event, StringBuffer responseBuffer) {
  final type = event['type'] as String?;

  switch (type) {
    case 'RUN_STARTED':
      print('  [RUN_STARTED] runId=${event['runId']}');
      break;

    case 'TEXT_MESSAGE_START':
      print('  [TEXT_MESSAGE_START] messageId=${event['messageId']}');
      break;

    case 'TEXT_MESSAGE_CONTENT':
      final delta = event['delta'] as String? ?? '';
      stdout.write(delta); // Stream content as it arrives
      responseBuffer.write(delta);
      break;

    case 'TEXT_MESSAGE_END':
      print('\n  [TEXT_MESSAGE_END]');
      break;

    case 'TOOL_CALL_START':
      print('  [TOOL_CALL_START] toolCallId=${event['toolCallId']} name=${event['toolCallName']}');
      break;

    case 'TOOL_CALL_ARGS':
      print('  [TOOL_CALL_ARGS] delta=${event['delta']}');
      break;

    case 'TOOL_CALL_END':
      print('  [TOOL_CALL_END]');
      break;

    case 'RUN_FINISHED':
      print('  [RUN_FINISHED] runId=${event['runId']}');
      break;

    case 'RUN_ERROR':
      print('  [RUN_ERROR] code=${event['code']} message=${event['message']}');
      break;

    case 'STATE_SNAPSHOT':
      print('  [STATE_SNAPSHOT]');
      break;

    case 'STATE_DELTA':
      print('  [STATE_DELTA]');
      break;

    case 'MESSAGES_SNAPSHOT':
      print('  [MESSAGES_SNAPSHOT] ${event['messages']?.length ?? 0} messages');
      break;

    default:
      print('  [UNKNOWN: $type] $event');
  }
}
