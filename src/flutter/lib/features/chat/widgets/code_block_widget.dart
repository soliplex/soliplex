import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Parses and renders message text with code blocks.
///
/// Detects ``` fenced code blocks and renders them with
/// syntax styling and individual copy buttons.
class MessageTextWithCodeBlocks extends StatelessWidget {
  const MessageTextWithCodeBlocks({
    required this.text,
    super.key,
    this.textStyle,
    this.onQuote,
  });
  final String text;
  final TextStyle? textStyle;
  final void Function(String quotedText)? onQuote;

  @override
  Widget build(BuildContext context) {
    final segments = _parseCodeBlocks(text);

    if (segments.length == 1 && !segments.first.isCode) {
      // No code blocks, just return selectable text with quote support
      return _SelectableTextWithQuote(
        text: text,
        style: textStyle,
        onQuote: onQuote,
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: segments.map((segment) {
        if (segment.isCode) {
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: _CodeBlock(
              code: segment.content,
              language: segment.language,
              onQuote: onQuote,
            ),
          );
        } else {
          return _SelectableTextWithQuote(
            text: segment.content,
            style: textStyle,
            onQuote: onQuote,
          );
        }
      }).toList(),
    );
  }

  /// Parse text into segments of regular text and code blocks.
  List<_TextSegment> _parseCodeBlocks(String text) {
    final segments = <_TextSegment>[];
    final codeBlockPattern = RegExp(
      r'```(\w*)\n?([\s\S]*?)```',
      multiLine: true,
    );

    var lastEnd = 0;
    for (final match in codeBlockPattern.allMatches(text)) {
      // Add text before code block
      if (match.start > lastEnd) {
        final before = text.substring(lastEnd, match.start).trim();
        if (before.isNotEmpty) {
          segments.add(_TextSegment(content: before, isCode: false));
        }
      }

      // Add code block
      final language = match.group(1) ?? '';
      final code = match.group(2) ?? '';
      segments.add(
        _TextSegment(content: code.trim(), isCode: true, language: language),
      );

      lastEnd = match.end;
    }

    // Add remaining text after last code block
    if (lastEnd < text.length) {
      final after = text.substring(lastEnd).trim();
      if (after.isNotEmpty) {
        segments.add(_TextSegment(content: after, isCode: false));
      }
    }

    // If no code blocks found, return original text
    if (segments.isEmpty) {
      segments.add(_TextSegment(content: text, isCode: false));
    }

    return segments;
  }
}

/// A segment of text (either regular text or code).
class _TextSegment {
  _TextSegment({required this.content, required this.isCode, this.language});
  final String content;
  final bool isCode;
  final String? language;
}

/// Selectable text with quote context menu option.
class _SelectableTextWithQuote extends StatelessWidget {
  const _SelectableTextWithQuote({
    required this.text,
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
      contextMenuBuilder: (context, editableTextState) {
        final selection = editableTextState.textEditingValue.selection;
        final selectedText = selection.textInside(text);

        return AdaptiveTextSelectionToolbar(
          anchors: editableTextState.contextMenuAnchors,
          children: [
            // Default copy button
            TextSelectionToolbarTextButton(
              padding: const EdgeInsets.all(8),
              onPressed: () {
                Clipboard.setData(ClipboardData(text: selectedText));
                editableTextState.hideToolbar();
              },
              child: const Text('Copy'),
            ),
            // Quote button (only if callback provided and text selected)
            if (onQuote != null && selectedText.isNotEmpty)
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
      },
    );
  }
}

/// Code block with copy button.
class _CodeBlock extends StatefulWidget {
  const _CodeBlock({required this.code, this.language, this.onQuote});
  final String code;
  final String? language;
  final void Function(String quotedText)? onQuote;

  @override
  State<_CodeBlock> createState() => _CodeBlockState();
}

class _CodeBlockState extends State<_CodeBlock> {
  bool _copied = false;

  Future<void> _copyCode() async {
    await Clipboard.setData(ClipboardData(text: widget.code));
    setState(() => _copied = true);
    Future<void>.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _copied = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header with language and copy button
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHigh,
              borderRadius: const BorderRadius.vertical(
                top: Radius.circular(7),
              ),
            ),
            child: Row(
              children: [
                if (widget.language?.isNotEmpty ?? false)
                  Text(
                    widget.language!,
                    style: TextStyle(
                      fontSize: 12,
                      color: colorScheme.onSurfaceVariant,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                const Spacer(),
                // Copy button
                InkWell(
                  onTap: _copyCode,
                  borderRadius: BorderRadius.circular(4),
                  child: Padding(
                    padding: const EdgeInsets.all(4),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          _copied ? Icons.check : Icons.copy_outlined,
                          size: 14,
                          color: _copied
                              ? Colors.green
                              : colorScheme.onSurfaceVariant,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          _copied ? 'Copied!' : 'Copy',
                          style: TextStyle(
                            fontSize: 12,
                            color: _copied
                                ? Colors.green
                                : colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
          // Code content
          Padding(
            padding: const EdgeInsets.all(12),
            child: SelectableText(
              widget.code,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 13,
                color: colorScheme.onSurface,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
