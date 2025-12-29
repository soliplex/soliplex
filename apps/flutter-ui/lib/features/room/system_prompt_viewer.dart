import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// A collapsible viewer for system prompts.
///
/// Shows a truncated preview by default, with option to expand.
/// Includes a copy button for developers.
class SystemPromptViewer extends StatefulWidget {
  const SystemPromptViewer({
    super.key,
    this.systemPrompt,
    this.previewLines = 3,
    this.initiallyExpanded = false,
  });
  final String? systemPrompt;
  final int previewLines;
  final bool initiallyExpanded;

  @override
  State<SystemPromptViewer> createState() => _SystemPromptViewerState();
}

class _SystemPromptViewerState extends State<SystemPromptViewer> {
  late bool _isExpanded;
  bool _copied = false;

  @override
  void initState() {
    super.initState();
    _isExpanded = widget.initiallyExpanded;
  }

  Future<void> _copyToClipboard() async {
    if (widget.systemPrompt == null) return;
    await Clipboard.setData(ClipboardData(text: widget.systemPrompt!));
    setState(() => _copied = true);
    Future<void>.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _copied = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    if (widget.systemPrompt == null || widget.systemPrompt!.isEmpty) {
      return const SizedBox.shrink();
    }

    final lines = widget.systemPrompt!.split('\n');
    final needsTruncation = lines.length > widget.previewLines;
    final displayText = _isExpanded || !needsTruncation
        ? widget.systemPrompt!
        : '${lines.take(widget.previewLines).join('\n')}...';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header with expand/collapse and copy
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Row(
            children: [
              Icon(
                Icons.description_outlined,
                size: 18,
                color: colorScheme.primary,
              ),
              const SizedBox(width: 8),
              Text(
                'System Prompt',
                style: theme.textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              const Spacer(),
              // Copy button
              Tooltip(
                message: _copied ? 'Copied!' : 'Copy prompt',
                child: InkWell(
                  onTap: _copyToClipboard,
                  borderRadius: BorderRadius.circular(16),
                  child: Padding(
                    padding: const EdgeInsets.all(4),
                    child: Icon(
                      _copied ? Icons.check : Icons.copy_outlined,
                      size: 16,
                      color: _copied
                          ? Colors.green
                          : colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ),
              if (needsTruncation)
                IconButton(
                  icon: Icon(
                    _isExpanded ? Icons.expand_less : Icons.expand_more,
                    size: 20,
                  ),
                  onPressed: () => setState(() => _isExpanded = !_isExpanded),
                  padding: const EdgeInsets.all(4),
                  constraints: const BoxConstraints(),
                  tooltip: _isExpanded ? 'Collapse' : 'Expand',
                ),
            ],
          ),
        ),

        // Prompt content
        Container(
          margin: const EdgeInsets.symmetric(horizontal: 12),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: colorScheme.outline.withValues(alpha: 0.2),
            ),
          ),
          child: SelectableText(
            displayText,
            style: theme.textTheme.bodySmall?.copyWith(
              fontFamily: 'monospace',
              color: colorScheme.onSurface,
              height: 1.5,
            ),
          ),
        ),
      ],
    );
  }
}

/// Compact system prompt preview (single line with truncation).
class SystemPromptPreview extends StatelessWidget {
  const SystemPromptPreview({
    super.key,
    this.systemPrompt,
    this.maxLength = 50,
  });
  final String? systemPrompt;
  final int maxLength;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    if (systemPrompt == null || systemPrompt!.isEmpty) {
      return Text(
        'No system prompt',
        style: theme.textTheme.bodySmall?.copyWith(
          color: colorScheme.onSurfaceVariant,
          fontStyle: FontStyle.italic,
        ),
      );
    }

    final truncated = systemPrompt!.length > maxLength
        ? '${systemPrompt!.substring(0, maxLength)}...'
        : systemPrompt!;

    // Replace newlines with spaces for compact display
    final singleLine = truncated
        .replaceAll('\n', ' ')
        .replaceAll(RegExp(r'\s+'), ' ');

    return Text(
      '"$singleLine"',
      style: theme.textTheme.bodySmall?.copyWith(
        color: colorScheme.onSurfaceVariant,
        fontStyle: FontStyle.italic,
      ),
      overflow: TextOverflow.ellipsis,
    );
  }
}
