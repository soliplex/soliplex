import 'package:flutter/material.dart';
import 'package:soliplex/core/models/chat_models.dart';

/// Compact, expandable summary of tool calls.
///
/// Collapsed: Shows "Used N tools" with overall status indicator
/// Expanded: Shows individual tool names with status icons
class ToolCallSummaryWidget extends StatelessWidget {
  const ToolCallSummaryWidget({
    required this.toolCalls,
    required this.isExpanded,
    required this.onToggle,
    super.key,
  });

  /// List of tool calls to display
  final List<ToolCallSummary> toolCalls;

  /// Whether the summary is expanded
  final bool isExpanded;

  /// Callback when expand/collapse is toggled
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    if (toolCalls.isEmpty) return const SizedBox.shrink();

    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      margin: const EdgeInsets.only(top: 8),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: colorScheme.outlineVariant.withValues(alpha: 0.5),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Header (always visible)
          _buildHeader(context, colorScheme),

          // Expanded list
          if (isExpanded) _buildExpandedList(context, colorScheme),
        ],
      ),
    );
  }

  Widget _buildHeader(BuildContext context, ColorScheme colorScheme) {
    final hasExecuting = toolCalls.any((t) => t.isExecuting);
    final hasError = toolCalls.any((t) => t.isError);
    final allCompleted = toolCalls.every((t) => t.isCompleted);

    // Determine overall status icon and color
    Widget statusIcon;
    Color statusColor;

    if (hasExecuting) {
      statusIcon = SizedBox(
        width: 14,
        height: 14,
        child: CircularProgressIndicator(
          strokeWidth: 2,
          color: colorScheme.primary,
        ),
      );
      statusColor = colorScheme.primary;
    } else if (hasError) {
      statusIcon = Icon(
        Icons.warning_amber_rounded,
        size: 16,
        color: colorScheme.error.withValues(alpha: 0.8),
      );
      statusColor = colorScheme.error.withValues(alpha: 0.8);
    } else if (allCompleted) {
      statusIcon = Icon(
        Icons.check_circle_outline,
        size: 16,
        color: colorScheme.onSurfaceVariant,
      );
      statusColor = colorScheme.onSurfaceVariant;
    } else {
      statusIcon = Icon(
        Icons.build_outlined,
        size: 16,
        color: colorScheme.onSurfaceVariant,
      );
      statusColor = colorScheme.onSurfaceVariant;
    }

    // Label text
    String label;
    if (hasExecuting) {
      final executingTools = toolCalls
          .where((t) => t.isExecuting)
          .map((t) => _formatToolName(t.toolName));
      if (toolCalls.length == 1) {
        label = 'Running ${executingTools.first}...';
      } else {
        label =
            'Running ${executingTools.length} of ${toolCalls.length} tools...';
      }
    } else {
      label =
          'Used ${toolCalls.length} tool${toolCalls.length == 1 ? '' : 's'}';
    }

    return InkWell(
      onTap: onToggle,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            statusIcon,
            const SizedBox(width: 8),
            Text(
              label,
              style: TextStyle(
                color: statusColor,
                fontSize: 12,
                fontWeight: hasExecuting ? FontWeight.w500 : FontWeight.normal,
              ),
            ),
            const SizedBox(width: 4),
            Icon(
              isExpanded ? Icons.expand_less : Icons.expand_more,
              size: 18,
              color: colorScheme.onSurfaceVariant,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildExpandedList(BuildContext context, ColorScheme colorScheme) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(10, 0, 10, 8),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: toolCalls.map((tool) {
          return _buildToolRow(context, tool, colorScheme);
        }).toList(),
      ),
    );
  }

  Widget _buildToolRow(
    BuildContext context,
    ToolCallSummary tool,
    ColorScheme colorScheme,
  ) {
    // Status icon
    Widget icon;
    if (tool.isExecuting) {
      icon = SizedBox(
        width: 12,
        height: 12,
        child: CircularProgressIndicator(
          strokeWidth: 1.5,
          color: colorScheme.primary,
        ),
      );
    } else if (tool.isCompleted) {
      icon = Icon(Icons.check, size: 14, color: colorScheme.onSurfaceVariant);
    } else if (tool.isError) {
      icon = Icon(
        Icons.close,
        size: 14,
        color: colorScheme.error.withValues(alpha: 0.8),
      );
    } else {
      icon = Icon(
        Icons.pending_outlined,
        size: 14,
        color: colorScheme.onSurfaceVariant,
      );
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(width: 4),
          icon,
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              _formatToolName(tool.toolName),
              style: TextStyle(
                color: tool.isError
                    ? colorScheme.error.withValues(alpha: 0.8)
                    : colorScheme.onSurfaceVariant,
                fontSize: 12,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (tool.isError && tool.errorMessage != null) ...[
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                _truncate(tool.errorMessage!, 30),
                style: TextStyle(
                  color: colorScheme.error.withValues(alpha: 0.6),
                  fontSize: 11,
                  fontStyle: FontStyle.italic,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ],
      ),
    );
  }

  /// Format tool name from snake_case to Title Case.
  String _formatToolName(String name) {
    return name
        .split('_')
        .map(
          (word) => word.isEmpty
              ? ''
              : '${word[0].toUpperCase()}${word.substring(1)}',
        )
        .join(' ');
  }

  String _truncate(String text, int maxLength) {
    if (text.length <= maxLength) return text;
    return '${text.substring(0, maxLength)}...';
  }
}

/// Compact inline tool call indicator (for single executing tool).
///
/// Shows a minimal "Running: Tool Name..." indicator inline.
class CompactToolCallIndicator extends StatelessWidget {
  const CompactToolCallIndicator({
    required this.toolName,
    required this.status,
    super.key,
  });
  final String toolName;
  final String status;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final isExecuting = status == 'executing';
    final isError = status.startsWith('error:');

    Widget icon;
    Color color;

    if (isExecuting) {
      icon = SizedBox(
        width: 12,
        height: 12,
        child: CircularProgressIndicator(
          strokeWidth: 1.5,
          color: colorScheme.primary,
        ),
      );
      color = colorScheme.primary;
    } else if (isError) {
      icon = Icon(
        Icons.close,
        size: 14,
        color: colorScheme.error.withValues(alpha: 0.8),
      );
      color = colorScheme.error.withValues(alpha: 0.8);
    } else {
      icon = Icon(Icons.check, size: 14, color: colorScheme.onSurfaceVariant);
      color = colorScheme.onSurfaceVariant;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          icon,
          const SizedBox(width: 6),
          Text(
            _formatToolName(toolName),
            style: TextStyle(
              color: color,
              fontSize: 12,
              fontStyle: FontStyle.italic,
            ),
          ),
        ],
      ),
    );
  }

  String _formatToolName(String name) {
    return name
        .split('_')
        .map(
          (word) => word.isEmpty
              ? ''
              : '${word[0].toUpperCase()}${word.substring(1)}',
        )
        .join(' ');
  }
}
