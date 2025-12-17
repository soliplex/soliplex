/// AG-UI (Agentic Generative UI) protocol implementation.
///
/// This library provides types and utilities for handling AG-UI events
/// from Server-Sent Events (SSE) streams, including:
///
/// - Event parsing and type-safe event classes
/// - Text message streaming buffer
/// - Tool call tracking and execution
/// - Thread management for conversation state
///
/// Example:
/// ```dart
/// import 'package:soliplex_client/src/agui/agui.dart';
///
/// // Parse SSE events
/// final event = AgUiEvent.fromJson(jsonData);
///
/// // Use buffers for streaming content
/// final textBuffer = TextMessageBuffer();
/// final toolCallBuffer = ToolCallBuffer();
///
/// // Register client-side tools
/// final registry = ToolRegistry();
/// registry.register(
///   name: 'calculator',
///   executor: (call) async => computeResult(call.arguments),
/// );
///
/// // Manage thread state
/// final thread = Thread(
///   transport: httpTransport,
///   roomId: 'room-123',
///   threadId: 'thread-456',
///   toolRegistry: registry,
/// );
/// ```
library agui;

export 'agui_event.dart';
export 'text_message_buffer.dart';
export 'thread.dart';
export 'tool_call_buffer.dart';
export 'tool_registry.dart';
