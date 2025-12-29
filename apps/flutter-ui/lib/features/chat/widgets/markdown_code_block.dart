import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Styled code block widget with copy button and quote support.
///
/// Use this in the `codeBuilder` of `SmoothMarkdown`.
class StyledCodeBlock extends StatefulWidget {
  const StyledCodeBlock({
    required this.code,
    this.language,
    this.onCopy,
    this.onQuote,
    super.key,
  });

  final String code;
  final String? language;
  final void Function(String code, String? language)? onCopy;
  final void Function(String quotedText)? onQuote;

  @override
  State<StyledCodeBlock> createState() => _StyledCodeBlockState();
}

class _StyledCodeBlockState extends State<StyledCodeBlock> {
  bool _copied = false;

  Future<void> _copyCode() async {
    await Clipboard.setData(ClipboardData(text: widget.code));
    widget.onCopy?.call(widget.code, widget.language);
    setState(() => _copied = true);
    Future<void>.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _copied = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 8),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header with language label and copy button
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
          // Code content with selection and quote support
          Padding(
            padding: const EdgeInsets.all(12),
            child: SelectableText(
              widget.code,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 13,
                color: colorScheme.onSurface,
              ),
              contextMenuBuilder: widget.onQuote != null
                  ? (context, editableTextState) {
                      final selection =
                          editableTextState.textEditingValue.selection;
                      final selectedText = selection.textInside(widget.code);

                      return AdaptiveTextSelectionToolbar(
                        anchors: editableTextState.contextMenuAnchors,
                        children: [
                          TextSelectionToolbarTextButton(
                            padding: const EdgeInsets.all(8),
                            onPressed: () {
                              Clipboard.setData(
                                ClipboardData(text: selectedText),
                              );
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
                                widget.onQuote!(quoted);
                                editableTextState.hideToolbar();
                              },
                              child: const Text('Quote'),
                            ),
                        ],
                      );
                    }
                  : null,
            ),
          ),
        ],
      ),
    );
  }
}
