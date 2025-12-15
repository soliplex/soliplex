import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// NoteCard widget for displaying text notes on the canvas.
///
/// Supports plain text and basic formatting. Used when sending
/// chat message content to the canvas.
class NoteCardWidget extends StatelessWidget {
  const NoteCardWidget({
    required this.content,
    super.key,
    this.title,
    this.sourceMessageId,
    this.color,
  });

  /// Create from JSON data.
  ///
  /// Expected data format:
  /// ```json
  /// {
  ///   "content": "The note text content",
  ///   "title": "Optional title",
  ///   "source_message_id": "uuid-of-source-message"
  /// }
  /// ```
  factory NoteCardWidget.fromData(
    Map<String, dynamic> data,
  ) {
    return NoteCardWidget(
      content: data['content'] as String? ?? '',
      title: data['title'] as String?,
      sourceMessageId: data['source_message_id'] as String?,
    );
  }
  final String content;
  final String? title;
  final String? sourceMessageId;
  final Color? color;

  void _copyToClipboard() {
    Clipboard.setData(ClipboardData(text: content));
  }

  /// Generate semantic ID for canvas deduplication.
  /// Uses content hash to prevent duplicate notes.
  static String semanticId(Map<String, dynamic> data) {
    final content = data['content'] as String? ?? '';
    final hash = content.hashCode.abs().toString();
    final shortHash = hash.length > 8 ? hash.substring(0, 8) : hash;
    return 'note-$shortHash';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final accentColor = color ?? theme.colorScheme.tertiary;

    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Header with icon and title
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: accentColor.withAlpha(20),
              borderRadius: const BorderRadius.vertical(
                top: Radius.circular(12),
              ),
            ),
            child: Row(
              children: [
                Icon(
                  Icons.sticky_note_2_outlined,
                  size: 18,
                  color: accentColor,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    title ?? 'Note',
                    style: theme.textTheme.titleSmall?.copyWith(
                      color: accentColor,
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.copy, size: 16),
                  onPressed: _copyToClipboard,
                  tooltip: 'Copy to clipboard',
                  visualDensity: VisualDensity.compact,
                  iconSize: 16,
                ),
              ],
            ),
          ),
          // Content
          Padding(
            padding: const EdgeInsets.all(12),
            child: SelectableText(content, style: theme.textTheme.bodyMedium),
          ),
        ],
      ),
    );
  }
}
