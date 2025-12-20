import 'package:equatable/equatable.dart';
import 'package:soliplex/core/models/error_types.dart';
import 'package:uuid/uuid.dart';

const _uuid = Uuid();

/// Represents a user in the chat system.
class ChatUser extends Equatable {
  const ChatUser({
    required this.id,
    this.firstName,
    this.lastName,
    this.profileImage,
    this.customProperties,
  });
  final String id;
  final String? firstName;
  final String? lastName;
  final String? profileImage;
  final Map<String, dynamic>? customProperties;

  String get displayName {
    if (firstName != null && lastName != null) {
      return '$firstName $lastName';
    }
    return firstName ?? lastName ?? id;
  }

  @override
  List<Object?> get props => [id, firstName, lastName, profileImage];

  /// Predefined user for the human user.
  static const ChatUser user = ChatUser(id: 'user', firstName: 'You');

  /// Predefined user for the AI agent.
  static const ChatUser agent = ChatUser(id: 'agent', firstName: 'Agent');

  /// Predefined user for system messages.
  static const ChatUser system = ChatUser(id: 'system', firstName: 'System');
}

/// Type of chat message content.
enum MessageType { text, genUi, loading, error, toolCall, toolCallGroup }

/// Status of a tool call execution.
enum ToolCallStatus { executing, completed, error }

/// Summary of a tool call for grouped display.
class ToolCallSummary extends Equatable {
  const ToolCallSummary({
    required this.toolCallId,
    required this.toolName,
    required this.status,
    required this.startedAt,
    this.errorMessage,
    this.completedAt,
  });
  final String toolCallId;
  final String toolName;
  final ToolCallStatus status;
  final String? errorMessage;
  final DateTime startedAt;
  final DateTime? completedAt;

  bool get isExecuting => status == ToolCallStatus.executing;
  bool get isCompleted => status == ToolCallStatus.completed;
  bool get isError => status == ToolCallStatus.error;

  ToolCallSummary copyWith({
    ToolCallStatus? status,
    String? errorMessage,
    DateTime? completedAt,
  }) {
    return ToolCallSummary(
      toolCallId: toolCallId,
      toolName: toolName,
      status: status ?? this.status,
      errorMessage: errorMessage ?? this.errorMessage,
      startedAt: startedAt,
      completedAt: completedAt ?? this.completedAt,
    );
  }

  @override
  List<Object?> get props => [
    toolCallId,
    toolName,
    status,
    errorMessage,
    startedAt,
    completedAt,
  ];
}

/// A citation from a RAG knowledge base response.
///
/// Contains metadata about the source document and the relevant chunk content.
class Citation extends Equatable {
  const Citation({
    required this.documentId,
    required this.chunkId,
    required this.documentUri,
    required this.content,
    this.documentTitle,
    this.pageNumbers = const [],
    this.headings,
  });

  /// Create a Citation from JSON data (as received from STATE_SNAPSHOT).
  factory Citation.fromJson(Map<String, dynamic> json) {
    return Citation(
      documentId: json['document_id'] as String? ?? '',
      chunkId: json['chunk_id'] as String? ?? '',
      documentUri: json['document_uri'] as String? ?? '',
      content: json['content'] as String? ?? '',
      documentTitle: json['document_title'] as String?,
      pageNumbers: (json['page_numbers'] as List<dynamic>?)
              ?.map((e) => e as int)
              .toList() ??
          const [],
      headings: (json['headings'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList(),
    );
  }

  /// Unique identifier for the source document.
  final String documentId;

  /// Unique identifier for the specific chunk within the document.
  final String chunkId;

  /// URI/path to the source document.
  final String documentUri;

  /// The actual text content of the cited chunk.
  final String content;

  /// Human-readable title of the document (may be null).
  final String? documentTitle;

  /// Page numbers where this chunk appears (may be empty).
  final List<int> pageNumbers;

  /// Section headings leading to this chunk (may be null).
  final List<String>? headings;

  /// Get a display title, falling back to filename from URI if no title.
  String get displayTitle {
    if (documentTitle != null && documentTitle!.isNotEmpty) {
      return documentTitle!;
    }
    // Extract filename from URI
    final uri = Uri.tryParse(documentUri);
    if (uri != null && uri.pathSegments.isNotEmpty) {
      return uri.pathSegments.last;
    }
    return 'Unknown Document';
  }

  /// Format page numbers for display (e.g., "p.1-3" or "p.5").
  String? get formattedPageNumbers {
    if (pageNumbers.isEmpty) return null;
    if (pageNumbers.length == 1) return 'p.${pageNumbers.first}';

    final sorted = [...pageNumbers]..sort();
    // Check if consecutive
    var isConsecutive = true;
    for (var i = 1; i < sorted.length; i++) {
      if (sorted[i] != sorted[i - 1] + 1) {
        isConsecutive = false;
        break;
      }
    }

    if (isConsecutive) {
      return 'p.${sorted.first}-${sorted.last}';
    } else {
      return 'p.${sorted.join(', ')}';
    }
  }

  @override
  List<Object?> get props => [
    documentId,
    chunkId,
    documentUri,
    content,
    documentTitle,
    pageNumbers,
    headings,
  ];
}

/// Represents a message in the chat.
class ChatMessage extends Equatable {
  ChatMessage({
    required this.user,
    String? id,
    DateTime? createdAt,
    this.type = MessageType.text,
    this.text,
    this.genUiContent,
    this.errorMessage,
    this.errorInfo,
    this.isStreaming = false,
    this.toolCallId,
    this.toolCallName,
    this.toolCallStatus,
    this.thinkingText,
    this.isThinkingStreaming = false,
    this.isThinkingExpanded = false,
    this.toolCalls,
    this.isToolGroupExpanded = false,
    this.citations = const [],
    this.isCitationsExpanded = false,
  }) : id = id ?? _uuid.v4(),
       createdAt = createdAt ?? DateTime.now();

  /// Create a text message.
  factory ChatMessage.text({
    required ChatUser user,
    required String text,
    String? id,
    DateTime? createdAt,
    bool isStreaming = false,
  }) {
    return ChatMessage(
      id: id,
      user: user,
      text: text,
      createdAt: createdAt,
      isStreaming: isStreaming,
    );
  }

  /// Create a GenUI message.
  factory ChatMessage.genUi({
    required ChatUser user,
    required GenUiContent content,
    String? id,
    DateTime? createdAt,
  }) {
    return ChatMessage(
      id: id,
      user: user,
      genUiContent: content,
      type: MessageType.genUi,
      toolCallId: content.toolCallId,
      createdAt: createdAt,
    );
  }

  /// Create a loading placeholder message.
  factory ChatMessage.loading({
    required ChatUser user,
    String? id,
    DateTime? createdAt,
  }) {
    return ChatMessage(
      id: id,
      user: user,
      type: MessageType.loading,
      createdAt: createdAt,
    );
  }

  /// Create an error message.
  factory ChatMessage.error({
    required ChatUser user,
    String? id,
    String? errorMessage,
    ChatErrorInfo? errorInfo,
    DateTime? createdAt,
  }) {
    return ChatMessage(
      id: id,
      user: user,
      type: MessageType.error,
      errorMessage: errorMessage ?? errorInfo?.technicalDetails,
      errorInfo: errorInfo,
      createdAt: createdAt,
    );
  }

  /// Create a tool call message.
  factory ChatMessage.toolCall({
    required ChatUser user,
    required String toolName,
    String? id,
    String? toolCallId,
    String status = 'executing',
    DateTime? createdAt,
  }) {
    return ChatMessage(
      id: id,
      user: user,
      type: MessageType.toolCall,
      toolCallName: toolName,
      toolCallId: toolCallId,
      toolCallStatus: status,
      createdAt: createdAt,
    );
  }

  /// Create a tool call group message.
  factory ChatMessage.toolCallGroup({
    required ChatUser user,
    required List<ToolCallSummary> toolCalls,
    String? id,
    bool isExpanded = false,
    DateTime? createdAt,
  }) {
    return ChatMessage(
      id: id,
      user: user,
      type: MessageType.toolCallGroup,
      toolCalls: toolCalls,
      isToolGroupExpanded: isExpanded,
      createdAt: createdAt,
    );
  }
  final String id;
  final ChatUser user;
  final DateTime createdAt;
  final MessageType type;
  final String? text;
  final GenUiContent? genUiContent;
  final String? errorMessage;
  final ChatErrorInfo? errorInfo;
  final bool isStreaming;
  final String? toolCallId;
  final String? toolCallName;
  final String? toolCallStatus;

  // Thinking fields
  final String? thinkingText;
  final bool isThinkingStreaming;
  final bool isThinkingExpanded;

  // Tool call group fields
  final List<ToolCallSummary>? toolCalls;
  final bool isToolGroupExpanded;

  // Citation fields
  final List<Citation> citations;
  final bool isCitationsExpanded;

  /// Create a copy with updated fields.
  ChatMessage copyWith({
    String? id,
    ChatUser? user,
    DateTime? createdAt,
    MessageType? type,
    String? text,
    GenUiContent? genUiContent,
    String? errorMessage,
    ChatErrorInfo? errorInfo,
    bool? isStreaming,
    String? toolCallId,
    String? toolCallName,
    String? toolCallStatus,
    String? thinkingText,
    bool? isThinkingStreaming,
    bool? isThinkingExpanded,
    List<ToolCallSummary>? toolCalls,
    bool? isToolGroupExpanded,
    List<Citation>? citations,
    bool? isCitationsExpanded,
  }) {
    return ChatMessage(
      id: id ?? this.id,
      user: user ?? this.user,
      createdAt: createdAt ?? this.createdAt,
      type: type ?? this.type,
      text: text ?? this.text,
      genUiContent: genUiContent ?? this.genUiContent,
      errorMessage: errorMessage ?? this.errorMessage,
      errorInfo: errorInfo ?? this.errorInfo,
      isStreaming: isStreaming ?? this.isStreaming,
      toolCallId: toolCallId ?? this.toolCallId,
      toolCallName: toolCallName ?? this.toolCallName,
      toolCallStatus: toolCallStatus ?? this.toolCallStatus,
      thinkingText: thinkingText ?? this.thinkingText,
      isThinkingStreaming: isThinkingStreaming ?? this.isThinkingStreaming,
      isThinkingExpanded: isThinkingExpanded ?? this.isThinkingExpanded,
      toolCalls: toolCalls ?? this.toolCalls,
      isToolGroupExpanded: isToolGroupExpanded ?? this.isToolGroupExpanded,
      citations: citations ?? this.citations,
      isCitationsExpanded: isCitationsExpanded ?? this.isCitationsExpanded,
    );
  }

  @override
  List<Object?> get props => [
    id,
    user,
    createdAt,
    type,
    text,
    genUiContent,
    errorMessage,
    errorInfo,
    isStreaming,
    toolCallId,
    toolCallName,
    toolCallStatus,
    thinkingText,
    isThinkingStreaming,
    isThinkingExpanded,
    toolCalls,
    isToolGroupExpanded,
    citations,
    isCitationsExpanded,
  ];
}

/// Content for a GenUI message.
///
/// Used with the native widget registry to render widgets
/// based on widgetName and data.
class GenUiContent extends Equatable {
  const GenUiContent({
    required this.toolCallId,
    required this.widgetName,
    this.data = const {},
  });
  final String toolCallId;
  final String widgetName;
  final Map<String, dynamic> data;

  GenUiContent copyWith({
    String? toolCallId,
    String? widgetName,
    Map<String, dynamic>? data,
  }) {
    return GenUiContent(
      toolCallId: toolCallId ?? this.toolCallId,
      widgetName: widgetName ?? this.widgetName,
      data: data ?? this.data,
    );
  }

  @override
  List<Object?> get props => [toolCallId, widgetName, data];
}
