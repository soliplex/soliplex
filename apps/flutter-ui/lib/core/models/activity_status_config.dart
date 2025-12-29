import 'package:soliplex/core/protocol/agui_event_types.dart';

/// Configuration for activity status indicator messages.
///
/// Defines personality messages shown during response generation,
/// with support for event-specific and tool-specific messages.
class ActivityStatusConfig {
  const ActivityStatusConfig({
    required this.idleMessages,
    this.eventMessages = const {},
    this.toolMessages = const {},
    this.cycleInterval = const Duration(seconds: 3),
    this.initialDelay = const Duration(milliseconds: 500),
  });

  /// Default messages shown when no specific event/tool context.
  final List<String> idleMessages;

  /// Messages shown for specific AG-UI event types.
  /// Keys are event type names (e.g., 'Thinking', 'TextMessageStart').
  final Map<String, List<String>> eventMessages;

  /// Messages shown for specific tool calls.
  /// Keys are tool names (e.g., 'get_location', 'canvas_render').
  final Map<String, List<String>> toolMessages;

  /// Time between cycling to the next message.
  final Duration cycleInterval;

  /// Delay before showing the first message after activity starts.
  final Duration initialDelay;

  /// Default configuration with personality messages.
  static const defaultConfig = ActivityStatusConfig(
    idleMessages: [
      'Thinking...',
      'Processing your request...',
      'Working on it...',
      'Analyzing...',
      'Considering options...',
    ],
    eventMessages: {
      AgUiEventTypes.thinking: [
        'Deep in thought...',
        'Reasoning through this...',
        'Contemplating...',
      ],
      AgUiEventTypes.textMessageStart: [
        'Composing response...',
        'Writing...',
        'Formulating answer...',
      ],
      AgUiEventTypes.toolCallStart: [
        'Using a tool...',
        'Taking action...',
        'Executing...',
      ],
      'ToolCallEnd': ['Tool completed...', 'Processing result...'],
    },
    toolMessages: {
      'get_location': ['Finding your location...', 'Locating...'],
      'canvas_render': ['Rendering to canvas...', 'Drawing...'],
      'genui_render': ['Generating UI...', 'Building interface...'],
      'search': ['Searching...', 'Looking for results...'],
      'web_search': ['Searching the web...', 'Browsing...'],
    },
  );

  /// Merge this config with another, with other taking precedence.
  ActivityStatusConfig merge(ActivityStatusConfig other) {
    return ActivityStatusConfig(
      idleMessages: other.idleMessages.isNotEmpty
          ? other.idleMessages
          : idleMessages,
      eventMessages: {...eventMessages, ...other.eventMessages},
      toolMessages: {...toolMessages, ...other.toolMessages},
      cycleInterval: other.cycleInterval,
      initialDelay: other.initialDelay,
    );
  }

  /// Get messages for a specific context.
  ///
  /// Priority: toolName > eventType > idle
  List<String> getMessages({String? eventType, String? toolName}) {
    // Tool-specific messages have highest priority
    if (toolName != null && toolMessages.containsKey(toolName)) {
      return toolMessages[toolName]!;
    }

    // Event-specific messages next
    if (eventType != null && eventMessages.containsKey(eventType)) {
      return eventMessages[eventType]!;
    }

    // Fall back to idle messages
    return idleMessages;
  }
}
