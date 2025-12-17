import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_smooth_markdown/flutter_smooth_markdown.dart';
import 'package:soliplex/core/services/markdown_hooks.dart';
import 'package:soliplex/features/chat/widgets/markdown_code_block.dart';
import 'package:soliplex/features/chat/widgets/tracked_markdown_image.dart'; // Added import
import 'package:url_launcher/url_launcher.dart';

/// MarkdownCard widget for displaying rich markdown content on the canvas.
///
/// Features:
/// - Full markdown rendering (headers, lists, links, etc.)
/// - Copy raw content button
/// - Selectable text
class MarkdownCardWidget extends ConsumerWidget {
  // Changed from StatelessWidget
  const MarkdownCardWidget({
    required this.content,
    super.key,
    this.title,
    this.sourceMessageId,
    this.messageId, // Added messageId to constructor
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
      messageId:
          data['source_message_id']
              as String?, // Use source_message_id for messageId
    );
  }
  final String content;
  final String? title;
  final String? sourceMessageId;
  final String? messageId; // Added messageId property

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
  Widget build(BuildContext context, WidgetRef ref) {
    // Added WidgetRef ref
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final hooks = ref.watch(markdownHooksProvider); // Retrieve hooks
    
    // Normalize line endings
    final normalizedContent =
        content.replaceAll('\r\n', '\n').replaceAll('\r', '\n');

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
            child: SmoothMarkdown(
              data: normalizedContent,
              styleSheet: MarkdownStyleSheet.fromTheme(theme).copyWith(
                paragraphStyle: theme.textTheme.bodyMedium,
                h1Style: theme.textTheme.headlineSmall,
                h2Style: theme.textTheme.titleLarge,
                h3Style: theme.textTheme.titleMedium,
                inlineCodeStyle: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 13,
                  backgroundColor: colorScheme.surfaceContainerHighest,
                ),
                codeBlockDecoration: BoxDecoration(
                  color: colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
              onTapLink: (href) {
                // Implemented onTapLink
                hooks.onLinkTap?.call(href, href, messageId ?? '');
                launchUrl(
                  Uri.parse(href),
                  mode: LaunchMode.externalApplication,
                );
              },
              imageBuilder: (uri, alt, title) {
                // Sanitize URI (remove surrounding angle brackets if present)
                var sanitizedUri = uri.trim();
                if (sanitizedUri.startsWith('<') &&
                    sanitizedUri.endsWith('>')) {
                  sanitizedUri =
                      sanitizedUri.substring(1, sanitizedUri.length - 1);
                }

                return TrackedMarkdownImage(
                  imageUrl: sanitizedUri,
                  messageId: messageId ?? '',
                );
              },
              codeBuilder: (code, language) {
                // Implemented codeBuilder
                return StyledCodeBlock(
                  code: code,
                  language: language,
                  onCopy: (code, language) {
                    hooks.onCodeCopy?.call(code, language, messageId ?? '');
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
