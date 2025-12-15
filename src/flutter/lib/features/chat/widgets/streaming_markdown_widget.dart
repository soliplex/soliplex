import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_streaming_text_markdown/flutter_streaming_text_markdown.dart';
import 'package:soliplex/core/services/markdown_hooks.dart';
import 'package:soliplex/features/chat/widgets/markdown_code_block.dart';
import 'package:soliplex/features/chat/widgets/tracked_markdown_image.dart';
import 'package:url_launcher/url_launcher.dart';

/// Widget that renders markdown with streaming animation support.
///
/// This widget provides two rendering modes:
/// - **Streaming mode** (`isStreaming=true`): Uses
/// [StreamingTextMarkdown.claude()]
///   for smooth character-by-character animation as text arrives.
/// - **Static mode** (`isStreaming=false`): Uses MarkdownBody with full
///   callbacks for links, images, and code blocks.
///
/// Example usage:
/// ```dart
/// StreamingMarkdownWidget(
///   text: message.text,
///   messageId: message.id,
///   isStreaming: message.isStreaming,
///   onQuote: (quotedText) {
///     // Insert quoted text into input field
///   },
/// )
/// ```
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
  /// Sanitize markdown to prevent flutter_markdown crashes.
  ///
  /// The flutter_markdown package fails with assertion `_inlines.isEmpty`
  /// when content has unclosed inline elements. This happens when streams
  /// are interrupted mid-message, leaving partial markdown.
  ///
  /// This function ensures:
  /// - Code blocks (```) are properly closed
  /// - Inline code (`) has matching delimiters
  String _sanitizeMarkdown(String text) {
    if (text.isEmpty) return text;

    var result = text;

    // Count fenced code blocks (```) - must be even
    final fencePattern = RegExp('^```', multiLine: true);
    final fenceCount = fencePattern.allMatches(result).length;
    if (fenceCount.isOdd) {
      // Close the unclosed code block
      result = '$result\n```';
    }

    // For inline code, count backticks outside of code blocks
    // This is tricky - for now, just ensure the total is manageable
    // by checking if there's an odd number of single backticks
    // that aren't part of triple backticks
    final lines = result.split('\n');
    var inCodeBlock = false;
    var inlineBackticks = 0;

    for (final line in lines) {
      if (line.startsWith('```')) {
        inCodeBlock = !inCodeBlock;
      } else if (!inCodeBlock) {
        // Count backticks in this line (simple heuristic)
        inlineBackticks += '`'.allMatches(line).length;
      }
    }

    // If odd number of inline backticks, append one to close
    if (inlineBackticks.isOdd) {
      result = '$result`';
    }

    return result;
  }

  @override
  Widget build(BuildContext context) {
    final hooks = ref.watch(markdownHooksProvider);
    final colorScheme = Theme.of(context).colorScheme;

    if (widget.isStreaming) {
      // Streaming mode - use animated markdown
      return StreamingTextMarkdown.claude(
        text: widget.text,
        onComplete: () {
          hooks.onStreamingComplete?.call();
        },
        theme: StreamingTextTheme(
          textStyle:
              widget.textStyle ??
              TextStyle(color: colorScheme.onSurface, fontSize: 14),
        ),
      );
    } else {
      // Finalized mode - use static markdown with full callbacks
      return _buildStaticMarkdown(context, hooks);
    }
  }

  Widget _buildStaticMarkdown(BuildContext context, MarkdownHooks hooks) {
    final colorScheme = Theme.of(context).colorScheme;

    // Sanitize markdown to prevent flutter_markdown crashes from
    // malformed content (e.g., unclosed code blocks from interrupted streams)
    final sanitizedText = _sanitizeMarkdown(widget.text);

    return MarkdownBody(
      data: sanitizedText,
      styleSheet: MarkdownStyleSheet(
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
      ), // Missing parenthesis here
      onTapLink: (text, href, title) {
        // Fire the hook callback
        hooks.onLinkTap?.call(href, text, widget.messageId);

        // Default behavior: open in browser
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
