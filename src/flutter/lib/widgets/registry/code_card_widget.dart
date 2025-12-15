import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// CodeCard widget for displaying code snippets on the canvas.
///
/// Features:
/// - Language badge in header
/// - Copy button with feedback
/// - Monospace font rendering
/// - Selectable text
class CodeCardWidget extends StatefulWidget {
  const CodeCardWidget({
    required this.code,
    super.key,
    this.language,
    this.title,
    this.sourceMessageId,
  });

  /// Create from JSON data.
  ///
  /// Expected data format:
  /// ```json
  /// {
  ///   "code": "print('hello')",
  ///   "language": "python",
  ///   "title": "Optional title",
  ///   "source_message_id": "uuid"
  /// }
  /// ```
  factory CodeCardWidget.fromData(
    Map<String, dynamic> data,
  ) {
    return CodeCardWidget(
      code: data['code'] as String? ?? '',
      language: data['language'] as String?,
      title: data['title'] as String?,
      sourceMessageId: data['source_message_id'] as String?,
    );
  }
  final String code;
  final String? language;
  final String? title;
  final String? sourceMessageId;

  /// Generate semantic ID for canvas deduplication.
  static String semanticId(Map<String, dynamic> data) {
    final code = data['code'] as String? ?? '';
    final lang = data['language'] as String? ?? 'code';
    final hash = code.hashCode.abs().toString();
    final shortHash = hash.length > 8 ? hash.substring(0, 8) : hash;
    return '$lang-$shortHash';
  }

  @override
  State<CodeCardWidget> createState() => _CodeCardWidgetState();
}

class _CodeCardWidgetState extends State<CodeCardWidget> {
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
    final displayLang = widget.language ?? 'code';

    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Header with language and copy button
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(color: colorScheme.surfaceContainerHigh),
            child: Row(
              children: [
                // Language badge
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: colorScheme.primaryContainer,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    displayLang,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: colorScheme.onPrimaryContainer,
                    ),
                  ),
                ),
                if (widget.title != null) ...[
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      widget.title!,
                      style: Theme.of(context).textTheme.titleSmall,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ] else
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
          Container(
            color: colorScheme.surfaceContainerHighest,
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
