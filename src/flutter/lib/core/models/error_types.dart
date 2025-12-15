/// Error type classification for chat errors
enum ChatErrorType {
  /// Network/connection failures, timeouts
  network,

  /// Server errors (500s, rate limits, etc.)
  server,

  /// Tool execution failures
  tool,
}

/// Structured error information for friendly display
class ChatErrorInfo {
  const ChatErrorInfo({
    required this.type,
    required this.friendlyMessage,
    this.technicalDetails,
    this.errorCode,
    this.toolName,
    this.canRetry = false,
  });

  /// Create a network error (connection issues, timeouts)
  factory ChatErrorInfo.network({String? details, bool canRetry = true}) {
    return ChatErrorInfo(
      type: ChatErrorType.network,
      friendlyMessage: 'Connection hiccup',
      technicalDetails: details,
      canRetry: canRetry,
    );
  }

  /// Create a server error (500s, rate limits, etc.)
  factory ChatErrorInfo.server({
    required String message,
    String? errorCode,
    String? details,
  }) {
    return ChatErrorInfo(
      type: ChatErrorType.server,
      friendlyMessage: 'Server had trouble with that',
      technicalDetails: details ?? message,
      errorCode: errorCode,
    );
  }

  /// Create a tool execution error
  factory ChatErrorInfo.tool({
    required String toolName,
    required String error,
  }) {
    return ChatErrorInfo(
      type: ChatErrorType.tool,
      friendlyMessage: "$toolName couldn't complete",
      technicalDetails: error,
      toolName: toolName,
    );
  }

  /// The type of error (determines display style)
  final ChatErrorType type;

  /// User-friendly message shown by default
  final String friendlyMessage;

  /// Technical details shown when expanded (optional)
  final String? technicalDetails;

  /// Error code from server (optional)
  final String? errorCode;

  /// Name of the tool that failed (for tool errors)
  final String? toolName;

  /// Whether a retry action should be offered
  final bool canRetry;

  /// Get the icon/emoji for this error type
  String get icon {
    switch (type) {
      case ChatErrorType.network:
        return '🔌';
      case ChatErrorType.server:
        return '😅';
      case ChatErrorType.tool:
        return '🔧';
    }
  }
}
