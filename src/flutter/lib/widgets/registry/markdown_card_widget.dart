import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';

/// MarkdownCard widget for displaying rich markdown content on the canvas.
///
/// Features:
/// - Full markdown rendering (headers, lists, links, etc.)
/// - Copy raw content button
/// - Selectable text
class MarkdownCardWidget extends StatelessWidget {
  const MarkdownCardWidget({
    required this.content,
    super.key,
    this.title,
    this.sourceMessageId,
  });

  /// Create from JSON data.
  ///
  /// Expected data format:
  /// ```json
  /// {
  ///   "content": "# Header\n\nSome **markdown** content",
  ///   "title": "Optional title",
  ///   "source_message_id": "uuid"
  /// }
  /// ```
  factory MarkdownCardWidget.fromData(
    Map<String, dynamic> data,
  ) {
    return MarkdownCardWidget(
      content: data['content'] as String? ?? '',
      title: data['title'] as String?,
      sourceMessageId: data['source_message_id'] as String?,
    );
  }
  final String content;
  final String? title;
  final String? sourceMessageId;

  void _copyToClipboard() {
    Clipboard.setData(ClipboardData(text: content));
  }

  /// Generate semantic ID for canvas deduplication.
  static String semanticId(Map<String, dynamic> data) {
    final content = data['content'] as String? ?? '';
    final hash = content.hashCode.abs().toString();
    final shortHash = hash.length > 8 ? hash.substring(0, 8) : hash;
    return 'markdown-$shortHash';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Header
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHigh,
              borderRadius: const BorderRadius.vertical(
                top: Radius.circular(12),
              ),
            ),
            child: Row(
              children: [
                Icon(
                  Icons.article_outlined,
                  size: 18,
                  color: colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    title ?? 'Markdown',
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.copy, size: 16),
                  onPressed: _copyToClipboard,
                  tooltip: 'Copy raw markdown',
                  visualDensity: VisualDensity.compact,
                  iconSize: 16,
                ),
              ],
            ),
          ),
          // Markdown content
          Padding(
            padding: const EdgeInsets.all(12),
            child: MarkdownBody(
              data: content,
              selectable: true,
              styleSheet: MarkdownStyleSheet.fromTheme(theme).copyWith(
                p: theme.textTheme.bodyMedium,
                h1: theme.textTheme.headlineSmall,
                h2: theme.textTheme.titleLarge,
                h3: theme.textTheme.titleMedium,
                code: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 13,
                  backgroundColor: colorScheme.surfaceContainerHighest,
                ),
                codeblockDecoration: BoxDecoration(
                  color: colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
