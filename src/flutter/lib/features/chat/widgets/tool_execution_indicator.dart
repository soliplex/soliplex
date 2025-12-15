import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/providers/panel_providers.dart';

/// Widget that displays active tool executions.
///
/// Shows a subtle notification bar when tools are executing,
/// with a spinner and the tool name(s).
///
/// Uses [activeToolExecutionProvider] for per-room scoped state,
/// ensuring tool indicators are isolated per room/server.
class ToolExecutionIndicator extends ConsumerWidget {
  const ToolExecutionIndicator({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final execState = ref.watch(activeToolExecutionProvider);

    if (!execState.hasActiveExecutions) {
      return const SizedBox.shrink();
    }

    final toolNames = execState.activeToolNames;
    final displayText = toolNames.length == 1
        ? 'Running: ${_formatToolName(toolNames.first)}'
        : 'Running ${toolNames.length} tools...';

    final primaryContainer = Theme.of(context).colorScheme.primaryContainer;
    final primary = Theme.of(context).colorScheme.primary;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      curve: Curves.easeOut,
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: primaryContainer.withValues(alpha: 0.8),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: primary.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: Theme.of(context).colorScheme.primary,
            ),
          ),
          const SizedBox(width: 10),
          Flexible(
            child: Text(
              displayText,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onPrimaryContainer,
                fontWeight: FontWeight.w500,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  /// Format tool name for display (convert snake_case to Title Case).
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

/// A more compact version of the indicator for tight spaces.
///
/// Uses [activeToolExecutionProvider] for per-room scoped state.
class ToolExecutionChip extends ConsumerWidget {
  const ToolExecutionChip({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final execState = ref.watch(activeToolExecutionProvider);

    if (!execState.hasActiveExecutions) {
      return const SizedBox.shrink();
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.secondaryContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: 12,
            height: 12,
            child: CircularProgressIndicator(
              strokeWidth: 1.5,
              color: Theme.of(context).colorScheme.secondary,
            ),
          ),
          const SizedBox(width: 6),
          Text(
            '${execState.activeCount}',
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: Theme.of(context).colorScheme.onSecondaryContainer,
            ),
          ),
        ],
      ),
    );
  }
}
