/// AG-UI Framework - Client-side infrastructure for reactive Flutter apps over AG-UI protocol
///
/// This framework provides a clean, reactive architecture for building Flutter
/// applications that communicate with AG-UI agents. It handles event streaming,
/// message parsing, state management, and provides a convenient API for both
/// chat and non-chat workflows.
///
/// ## Core Concepts
///
/// - **AguiThread**: A conversation with an agent, composed of one or more runs
/// - **Run**: A single request-response cycle, self-contained and stateful
/// - **EventParser**: Stateful parser that accumulates chunked events into complete messages
///
/// ## Features
///
/// - Stream-based reactive architecture
/// - Historical message replay for new listeners
/// - Multiple agents per thread support
/// - Built-in state tracking
/// - Optional persistence layer
/// - UI-agnostic message filtering
///
/// ## Example Usage
///
/// ```dart
/// // Create a thread
/// final thread = AguiThread(
///   id: 'thread_123',
///   client: agUiClient,
///   agentName: 'my-agent',
///   clientTools: [
///     Tool(name: 'approve', description: '...', parameters: {}),
///   ],
/// );
///
/// // Listen to messages
/// thread.messageStream.textMessages.listen((message) {
///   // Update UI
/// });
///
/// // Send a message
/// await thread.sendMessage('Hello!');
///
/// // Respond to tool call
/// await thread.sendToolResult('tool_123', 'APPROVED');
/// ```
library;

export 'domain/thread.dart';
export 'domain/run.dart';
export 'domain/tool_call_registry.dart';
export 'parsing/event_parser.dart';
export 'parsing/parse_result.dart';
export 'extensions/message_stream_extensions.dart';
