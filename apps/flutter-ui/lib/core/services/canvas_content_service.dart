import 'dart:convert';

/// Content types that can be sent to the canvas.
enum CanvasContentType {
  /// Plain text - rendered as NoteCard
  plainText,

  /// Markdown with formatting - rendered as MarkdownCard
  markdown,

  /// Fenced code block - rendered as CodeCard
  codeBlock,

  /// JSON with widget_name - uses existing widget registry
  jsonWidget,
}

/// Result of content analysis.
class CanvasContentAnalysis {
  const CanvasContentAnalysis({
    required this.type,
    required this.widgetName,
    required this.data,
    this.metadata = const {},
  });

  /// The detected content type
  final CanvasContentType type;

  /// The widget name to use for rendering
  final String widgetName;

  /// The data to pass to the widget
  final Map<String, dynamic> data;

  /// Additional metadata (e.g., language for code)
  final Map<String, dynamic> metadata;
}

/// Service for analyzing chat content and preparing it for the canvas.
///
/// Detects content type (JSON widget, code block, markdown, plain text)
/// and returns the appropriate widget name and data for canvas rendering.
class CanvasContentService {
  /// Analyze content and return canvas-ready widget info.
  ///
  /// Detection priority:
  /// 1. JSON with widget_name → use existing widget from registry
  /// 2. Fenced code block (```lang) → CodeCard
  /// 3. Markdown with formatting → MarkdownCard
  /// 4. Plain text → NoteCard
  CanvasContentAnalysis analyze(String content, {String? sourceMessageId}) {
    final trimmed = content.trim();

    // 1. Check for JSON with widget_name
    final jsonWidget = _tryParseJsonWidget(trimmed);
    if (jsonWidget != null) {
      return jsonWidget;
    }

    // 2. Check for fenced code block
    final codeBlock = _tryParseCodeBlock(trimmed);
    if (codeBlock != null) {
      return CanvasContentAnalysis(
        type: CanvasContentType.codeBlock,
        widgetName: 'CodeCard',
        data: {
          'code': codeBlock.code,
          'language': codeBlock.language,
          'source_message_id': ?sourceMessageId,
        },
        metadata: {'language': codeBlock.language},
      );
    }

    // 3. Check for markdown formatting
    if (_hasMarkdownFormatting(trimmed)) {
      return CanvasContentAnalysis(
        type: CanvasContentType.markdown,
        widgetName: 'MarkdownCard',
        data: {
          'content': trimmed,
          'source_message_id': ?sourceMessageId,
        },
      );
    }

    // 4. Default to plain text note
    return CanvasContentAnalysis(
      type: CanvasContentType.plainText,
      widgetName: 'NoteCard',
      data: {
        'content': trimmed,
        'source_message_id': ?sourceMessageId,
      },
    );
  }

  /// Try to parse content as JSON with widget_name field.
  CanvasContentAnalysis? _tryParseJsonWidget(String content) {
    // Must start with { to be JSON
    if (!content.startsWith('{')) return null;

    try {
      final parsed = jsonDecode(content);
      if (parsed is! Map<String, dynamic>) return null;

      // Check for widget_name field
      final widgetName = parsed['widget_name'] as String?;
      if (widgetName == null) return null;

      // Extract data - either from 'data' field or the whole object (minus
      // widget_name)
      Map<String, dynamic> data;
      if (parsed.containsKey('data') && parsed['data'] is Map) {
        data = Map<String, dynamic>.from(parsed['data'] as Map);
      } else {
        data = Map<String, dynamic>.from(parsed);
        data.remove('widget_name');
      }

      return CanvasContentAnalysis(
        type: CanvasContentType.jsonWidget,
        widgetName: widgetName,
        data: data,
        metadata: {'original_json': content},
      );
    } on Object catch (_) {
      return null;
    }
  }

  /// Try to extract a fenced code block.
  _CodeBlock? _tryParseCodeBlock(String content) {
    // Match ```language\ncode\n```
    final regex = RegExp(r'^```(\w*)\n([\s\S]*?)\n```$');
    final match = regex.firstMatch(content);
    if (match == null) return null;

    final language = match.group(1);
    final code = match.group(2) ?? '';

    return _CodeBlock(
      code: code.trim(),
      language: language?.isNotEmpty ?? false ? language : null,
    );
  }

  /// Check if content has markdown formatting.
  bool _hasMarkdownFormatting(String content) {
    // Headers
    if (RegExp(r'^#{1,6}\s', multiLine: true).hasMatch(content)) return true;

    // Bold/italic
    if (content.contains('**') || content.contains('__')) return true;
    if (RegExp(r'(?<!\*)\*(?!\*)').hasMatch(content) ||
        RegExp('(?<!_)_(?!_)').hasMatch(content)) {
      return true;
    }

    // Lists
    if (RegExp(r'^[-*+]\s', multiLine: true).hasMatch(content)) return true;
    if (RegExp(r'^\d+\.\s', multiLine: true).hasMatch(content)) return true;

    // Links
    if (RegExp(r'\[.+\]\(.+\)').hasMatch(content)) return true;

    // Inline code (but not fenced blocks)
    if (RegExp('`[^`]+`').hasMatch(content)) return true;

    // Blockquotes
    if (RegExp(r'^>\s', multiLine: true).hasMatch(content)) return true;

    return false;
  }
}

/// Helper class for code block parsing.
class _CodeBlock {
  _CodeBlock({required this.code, this.language});
  final String code;
  final String? language;
}
