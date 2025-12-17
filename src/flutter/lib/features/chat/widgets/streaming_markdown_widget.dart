import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart' as md;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_smooth_markdown/flutter_smooth_markdown.dart' as smooth;
import 'package:soliplex/core/services/markdown_hooks.dart';
import 'package:soliplex/features/chat/widgets/markdown_code_block.dart';
import 'package:soliplex/features/chat/widgets/tracked_markdown_image.dart';
import 'package:url_launcher/url_launcher.dart';

/// Widget that renders markdown with streaming animation support.
///
/// Uses [smooth.SmoothMarkdown] for robust, crash-free streaming rendering.
class StreamingMarkdownWidget extends ConsumerStatefulWidget {
  const StreamingMarkdownWidget({
    required this.text,
    required this.messageId,
    required this.isStreaming,
    super.key,
    this.textStyle,
    this.onQuote,
  });

  /// The markdown text to render
  final String text;

  /// Unique identifier for the message (used for tracking)
  final String messageId;

  /// Whether the message is currently streaming
  final bool isStreaming;

  /// Optional text style for the content
  final TextStyle? textStyle;

  /// Callback when text is quoted (via context menu)
  final void Function(String quotedText)? onQuote;

  @override
  ConsumerState<StreamingMarkdownWidget> createState() =>
      _StreamingMarkdownWidgetState();
}

class _StreamingMarkdownWidgetState
    extends ConsumerState<StreamingMarkdownWidget> {
  @override
  Widget build(BuildContext context) {
    final hooks = ref.watch(markdownHooksProvider);
    final colorScheme = Theme.of(context).colorScheme;

    // Use SmoothMarkdown for streaming to handle partial updates gracefully
    // and provide typing animation.
    if (widget.isStreaming) {
      return smooth.SmoothMarkdown(
        data: widget.text,
        styleSheet: smooth.MarkdownStyleSheet(
          paragraphStyle:
              widget.textStyle ??
              TextStyle(color: colorScheme.onSurface, fontSize: 14),
          inlineCodeStyle: TextStyle(
            fontFamily: 'monospace',
            fontSize: 13,
            color: colorScheme.onSurface,
            backgroundColor: colorScheme.surfaceContainerHighest,
          ),
          codeBlockStyle: TextStyle(
            fontFamily: 'monospace',
            fontSize: 13,
            color: colorScheme.onSurface,
            // Background is handled by decoration
          ),
          codeBlockDecoration: BoxDecoration(
            color: colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(8),
          ),
          linkStyle: TextStyle(
            color: colorScheme.primary,
            decoration: TextDecoration.underline,
          ),
          h1Style: TextStyle(
            fontSize: 24,
            fontWeight: FontWeight.bold,
            color: colorScheme.onSurface,
          ),
          h2Style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: colorScheme.onSurface,
          ),
          h3Style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.bold,
            color: colorScheme.onSurface,
          ),
          blockquoteDecoration: BoxDecoration(
            color: colorScheme.surfaceContainerHighest,
            border: Border(
              left: BorderSide(color: colorScheme.primary, width: 4),
            ),
          ),
          blockquotePadding: const EdgeInsets.all(12),
          listBulletStyle: TextStyle(color: colorScheme.onSurface),
        ),
      );
    }

    // Use static MarkdownBody for finished messages to ensure full
    // interactivity (copy/paste, etc) which might be limited in the
    // streaming widget.
    return md.MarkdownBody(
      data: widget.text,
      styleSheet: md.MarkdownStyleSheet(
        p:
            widget.textStyle ??
            TextStyle(color: colorScheme.onSurface, fontSize: 14),
        code: TextStyle(
          fontFamily: 'monospace',
          fontSize: 13,
          color: colorScheme.onSurface,
          backgroundColor: colorScheme.surfaceContainerHighest,
        ),
        codeblockDecoration: BoxDecoration(
          color: colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(8),
        ),
        a: TextStyle(
          color: colorScheme.primary,
          decoration: TextDecoration.underline,
        ),
        h1: TextStyle(
          fontSize: 24,
          fontWeight: FontWeight.bold,
          color: colorScheme.onSurface,
        ),
        h2: TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.bold,
          color: colorScheme.onSurface,
        ),
        h3: TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.bold,
          color: colorScheme.onSurface,
        ),
        blockquoteDecoration: BoxDecoration(
          color: colorScheme.surfaceContainerHighest,
          border: Border(
            left: BorderSide(color: colorScheme.primary, width: 4),
          ),
        ),
        blockquotePadding: const EdgeInsets.all(12),
        listBullet: TextStyle(color: colorScheme.onSurface),
      ),
      onTapLink: (text, href, title) {
        hooks.onLinkTap?.call(href, text, widget.messageId);
        if (href != null) {
          launchUrl(Uri.parse(href), mode: LaunchMode.externalApplication);
        }
      },
      imageBuilder: (uri, title, alt) {
        return TrackedMarkdownImage(
          imageUrl: uri.toString(),
          messageId: widget.messageId,
        );
      },
      builders: {
        'pre': MarkdownCodeBlockBuilder(
          onCopy: (code, language) {
            hooks.onCodeCopy?.call(code, language, widget.messageId);
          },
          onQuote: widget.onQuote != null
              ? (quotedText) {
                  hooks.onQuote?.call(quotedText, widget.messageId);
                  widget.onQuote?.call(quotedText);
                }
              : null,
          messageId: widget.messageId,
        ),
      },
    );
  }
}

/// Selectable text widget with quote support via context menu.
///
/// This is used for non-markdown text or when you need custom
/// selection behavior.
class SelectableTextWithQuote extends StatelessWidget {
  const SelectableTextWithQuote({
    required this.text,
    super.key,
    this.style,
    this.onQuote,
  });
  final String text;
  final TextStyle? style;
  final void Function(String quotedText)? onQuote;

  @override
  Widget build(BuildContext context) {
    return SelectableText(
      text,
      style: style,
      contextMenuBuilder: onQuote != null
          ? (context, editableTextState) {
              final selection = editableTextState.textEditingValue.selection;
              final selectedText = selection.textInside(text);

              return AdaptiveTextSelectionToolbar(
                anchors: editableTextState.contextMenuAnchors,
                children: [
                  TextSelectionToolbarTextButton(
                    padding: const EdgeInsets.all(8),
                    onPressed: () {
                      Clipboard.setData(ClipboardData(text: selectedText));
                      editableTextState.hideToolbar();
                    },
                    child: const Text('Copy'),
                  ),
                  if (selectedText.isNotEmpty)
                    TextSelectionToolbarTextButton(
                      padding: const EdgeInsets.all(8),
                      onPressed: () {
                        final quoted = selectedText
                            .split('\n')
                            .map((line) => '> $line')
                            .join('\n');
                        onQuote!(quoted);
                        editableTextState.hideToolbar();
                      },
                      child: const Text('Quote'),
                    ),
                ],
              );
            }
          : null,
    );
  }
}
