import 'package:flutter/material.dart';
import 'package:flutter_smooth_markdown/flutter_smooth_markdown.dart';
import 'package:flutter_streaming_text_markdown/flutter_streaming_text_markdown.dart';

/// Collapsible thinking section that appears above message content.
///
/// Shows AI reasoning/thinking in a muted, expandable section.
/// Auto-expands while streaming, auto-collapses when complete.
class CollapsibleThinkingWidget extends StatelessWidget {
  const CollapsibleThinkingWidget({
    required this.thinkingText,
    required this.isStreaming,
    required this.isExpanded,
    required this.onToggle,
    super.key,
  });

  /// The thinking text content
  final String thinkingText;

  /// Whether thinking is currently streaming
  final bool isStreaming;

  /// Whether the section is expanded
  final bool isExpanded;

  /// Callback when expand/collapse is toggled
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Container(
        decoration: BoxDecoration(
          color: colorScheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: colorScheme.outlineVariant.withValues(alpha: 0.5),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Header
            _buildHeader(context, colorScheme),

            // Content (when expanded)
            if (isExpanded) _buildContent(context, colorScheme),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context, ColorScheme colorScheme) {
    final charCount = thinkingText.length;

    return InkWell(
      onTap: isStreaming ? null : onToggle,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: [
            // Brain icon with subtle animation while streaming
            if (isStreaming)
              _PulsingIcon(icon: Icons.psychology, color: colorScheme.primary)
            else
              Icon(
                Icons.psychology_outlined,
                size: 18,
                color: colorScheme.onSurfaceVariant,
              ),
            const SizedBox(width: 8),

            // Label
            Expanded(
              child: Text(
                isStreaming
                    ? 'Thinking...'
                    : 'View reasoning ($charCount chars)',
                style: TextStyle(
                  color: isStreaming
                      ? colorScheme.primary
                      : colorScheme.onSurfaceVariant,
                  fontSize: 13,
                  fontWeight: isStreaming ? FontWeight.w500 : FontWeight.normal,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ),

            // Expand/collapse icon (only when not streaming)
            if (!isStreaming)
              Icon(
                isExpanded ? Icons.expand_less : Icons.expand_more,
                size: 20,
                color: colorScheme.onSurfaceVariant,
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent(BuildContext context, ColorScheme colorScheme) {
    // Normalize line endings
    final normalizedText =
        thinkingText.replaceAll('\r\n', '\n').replaceAll('\r', '\n');

    return Container(
      constraints: const BoxConstraints(maxHeight: 300),
      margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      child: SingleChildScrollView(
        child: isStreaming
            ? StreamingTextMarkdown.claude(
                text: normalizedText,
                theme: StreamingTextTheme(
                  textStyle: TextStyle(
                    color: colorScheme.onSurfaceVariant,
                    fontSize: 13,
                    height: 1.5,
                  ),
                ),
              )
            : SmoothMarkdown(
                data: normalizedText,
                styleSheet: MarkdownStyleSheet.fromTheme(
                  Theme.of(context),
                ).copyWith(
                  paragraphStyle: TextStyle(
                    color: colorScheme.onSurfaceVariant,
                    fontSize: 13,
                    height: 1.5,
                  ),
                  inlineCodeStyle: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 12,
                    color: colorScheme.onSurfaceVariant,
                    backgroundColor: colorScheme.surfaceContainerHighest,
                  ),
                  codeBlockDecoration: BoxDecoration(
                    color: colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(6),
                  ),
                ),
              ),
      ),
    );
  }
}

/// Pulsing icon animation for streaming state.
class _PulsingIcon extends StatefulWidget {
  const _PulsingIcon({required this.icon, required this.color});
  final IconData icon;
  final Color color;

  @override
  State<_PulsingIcon> createState() => _PulsingIconState();
}

class _PulsingIconState extends State<_PulsingIcon>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 1000),
      vsync: this,
    )..repeat(reverse: true);

    _animation = Tween<double>(
      begin: 0.5,
      end: 1,
    ).animate(CurvedAnimation(parent: _controller, curve: Curves.easeInOut));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _animation,
      builder: (context, child) {
        return Opacity(
          opacity: _animation.value,
          child: Icon(widget.icon, size: 18, color: widget.color),
        );
      },
    );
  }
}
