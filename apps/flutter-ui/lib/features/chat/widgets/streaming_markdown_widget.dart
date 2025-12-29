import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_smooth_markdown/flutter_smooth_markdown.dart';
import 'package:soliplex/core/services/markdown_hooks.dart';
import 'package:soliplex/features/chat/widgets/markdown_code_block.dart';
import 'package:soliplex/features/chat/widgets/tracked_markdown_image.dart';
import 'package:url_launcher/url_launcher.dart';

/// Widget that renders markdown with streaming animation support.
///
/// Uses [SmoothMarkdown] for robust, crash-free rendering.
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

    // Normalize line endings to prevent parsing issues with CRLF
    var normalizedText =
        widget.text.replaceAll('\r\n', '\n').replaceAll('\r', '\n');

    // Strip outer markdown code block if present
    // Matches ```markdown ... ``` or ```md ... ```
    // Only strip if the body doesn't contain nested fences
    // (which would mean it's not a single wrapper)
    final wrapperMatch = RegExp(
      r'^```(?:markdown|md)\s*\n(.*)\n```\s*$',
      dotAll: true,
    ).firstMatch(normalizedText);

    if (wrapperMatch != null) {
      final body = wrapperMatch.group(1)!;
      // Safety check: ensure the body doesn't contain fences that
      // would break structure
      if (!body.startsWith('```') && !body.contains('\n```')) {
        normalizedText = body;
      }
    }

    return SmoothMarkdown(
      data: normalizedText,
      styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
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
      onTapLink: (href) {
        hooks.onLinkTap?.call(href, href, widget.messageId);
        launchUrl(Uri.parse(href), mode: LaunchMode.externalApplication);
      },
      imageBuilder: (uri, alt, title) {
        // Sanitize URI (remove surrounding angle brackets if present)
        var sanitizedUri = uri.trim();
        if (sanitizedUri.startsWith('<') && sanitizedUri.endsWith('>')) {
          sanitizedUri = sanitizedUri.substring(1, sanitizedUri.length - 1);
        }

        return TrackedMarkdownImage(
          imageUrl: sanitizedUri,
          messageId: widget.messageId,
        );
      },
      codeBuilder: (code, language) {
        return StyledCodeBlock(
          code: code,
          language: language,
          onCopy: (code, language) {
            hooks.onCodeCopy?.call(code, language, widget.messageId);
          },
          onQuote: widget.onQuote != null
              ? (quotedText) {
                  hooks.onQuote?.call(quotedText, widget.messageId);
                  widget.onQuote?.call(quotedText);
                }
              : null,
        );
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
