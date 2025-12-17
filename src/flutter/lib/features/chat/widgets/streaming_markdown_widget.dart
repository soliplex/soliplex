import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex/core/services/markdown_hooks.dart';
import 'package:soliplex/features/chat/widgets/markdown_code_block.dart';
import 'package:soliplex/features/chat/widgets/tracked_markdown_image.dart';
import 'package:url_launcher/url_launcher.dart';

/// Widget that renders markdown with streaming animation support.
///
/// This widget provides two rendering modes:
/// - **Streaming mode** (`isStreaming=true`): Uses a custom adaptive
///   typewriter effect to smoothly reveal text as it arrives, handling
///   variable network speeds without stuttering.
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
    extends ConsumerState<StreamingMarkdownWidget>
    with SingleTickerProviderStateMixin {
  late final Ticker _ticker;
  String _displayedText = '';
  int _currentLength = 0;

  @override
  void initState() {
    super.initState();
    // Initialize with full text if not streaming, or start from 0 if streaming
    // (though usually streaming starts with empty text anyway)
    _currentLength = widget.isStreaming ? 0 : widget.text.length;
    _displayedText = widget.isStreaming
        ? ''
        : widget.text.substring(0, _currentLength); // Safety

    _ticker = createTicker(_onTick);
    if (widget.isStreaming) {
      _ticker.start();
    }
  }

  @override
  void didUpdateWidget(StreamingMarkdownWidget oldWidget) {
    super.didUpdateWidget(oldWidget);

    // Start/Stop ticker based on streaming state
    if (widget.isStreaming && !_ticker.isActive) {
      _ticker.start();
    } else if (!widget.isStreaming && _ticker.isActive) {
      _ticker.stop();
      // Snap to full text when streaming stops
      _currentLength = widget.text.length;
      _displayedText = widget.text;
    }

    // If not streaming, always ensure we show full text (e.g. edits/history)
    if (!widget.isStreaming) {
      _currentLength = widget.text.length;
      _displayedText = widget.text;
    }
  }

  @override
  void dispose() {
    _ticker.dispose();
    super.dispose();
  }

  void _onTick(Duration elapsed) {
    final targetLength = widget.text.length;

    // If we've caught up (or text shrank), sync and stop doing work
    if (_currentLength >= targetLength) {
      if (_currentLength > targetLength) {
        // Handle text shrinking (e.g. correction)
        _currentLength = targetLength;
        setState(() {
          _displayedText = widget.text;
        });
      }
      return;
    }

    // Adaptive Speed Logic:
    // Determine how many characters to reveal this frame.
    //
    // - Base speed: 1 char per frame (~60 chars/sec) - fast but readable type
    // - Catch-up: If lag is large (burst of data), increase speed proportional
    //   to distance.
    final distance = targetLength - _currentLength;

    // Accelerate as distance grows.
    // Example:
    // Lag 10 chars -> add 1 char (Base)
    // Lag 50 chars -> add 1 + 1 = 2 chars
    // Lag 200 chars -> add 1 + 4 = 5 chars
    // This ensures we never fall too far behind even with fast tokens.
    var charsToAdd = 1 + (distance ~/ 40);

    // Cap excessive jumps to avoid jumpiness, unless extremely behind
    if (charsToAdd > 10) charsToAdd = 10;

    var nextLength = _currentLength + charsToAdd;
    if (nextLength > targetLength) nextLength = targetLength;

    setState(() {
      _currentLength = nextLength;
      // Using substring is efficient enough for typical chat message sizes
      _displayedText = widget.text.substring(0, _currentLength);
    });
  }

  /// Sanitize markdown to prevent flutter_markdown crashes.
  ///
  /// The flutter_markdown package fails with assertion `_inlines.isEmpty`
  /// when content has unclosed inline elements. This happens when streams
  /// are interrupted mid-message, leaving partial markdown.
  ///
  /// This function ensures:
  /// - Code blocks (```) are properly closed
  /// - Inline code (`) has matching delimiters
  /// - Brackets ([) and Parentheses (() are balanced (simple heuristic)
  String _sanitizeMarkdown(String text) {
    if (text.isEmpty) return text;

    final sb = StringBuffer(text);
    var inFence = false;
    var inInlineCode = false;
    var openBrackets = 0;
    var openParens = 0;

    for (var i = 0; i < text.length; i++) {
      final char = text[i];

      if (char == '`') {
        final isFence =
            i + 2 < text.length && text[i + 1] == '`' && text[i + 2] == '`';

        if (inFence) {
          if (isFence) {
            inFence = false;
            i += 2;
          }
        } else if (inInlineCode) {
          if (!isFence) {
            inInlineCode = false;
          }
        } else {
          if (isFence) {
            inFence = true;
            i += 2;
          } else {
            inInlineCode = true;
          }
        }
        continue;
      }

      if (inFence || inInlineCode) continue;

      if (char == '[') {
        openBrackets++;
      } else if (char == ']') {
        if (openBrackets > 0) openBrackets--;
      } else if (char == '(') {
        openParens++;
      } else if (char == ')') {
        if (openParens > 0) openParens--;
      }
    }

    if (inFence) sb.write('\n```');
    if (inInlineCode) sb.write('`');
    while (openBrackets > 0) {
      sb.write(']');
      openBrackets--;
    }
    while (openParens > 0) {
      sb.write(')');
      openParens--;
    }

    return sb.toString();
  }

  @override
  Widget build(BuildContext context) {
    final hooks = ref.watch(markdownHooksProvider);

    // Use our custom locally-buffered text for both modes.
    // When streaming, _displayedText updates frame-by-frame via _onTick.
    // When static, _displayedText is just widget.text.
    //
    // Pass the _sanitizeMarkdown version to the builder to ensure safety.
    return _buildStaticMarkdown(context, hooks, _displayedText);
  }

  Widget _buildStaticMarkdown(
    BuildContext context,
    MarkdownHooks hooks,
    String content,
  ) {
    final colorScheme = Theme.of(context).colorScheme;

    // Sanitize markdown to prevent flutter_markdown crashes from
    // malformed content (e.g., unclosed code blocks from interrupted streams)
    final sanitizedText = _sanitizeMarkdown(content);

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
