import 'package:flutter/material.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/shared/utils/date_formatter.dart';

/// A list item widget that displays a thread's information.
///
/// Shows:
/// - Thread name (or "Thread {shortId}" if no name)
/// - Relative timestamp of last update
/// - Highlight if selected
/// - Activity indicator if run is active on this thread
///
/// Example:
/// ```dart
/// ThreadListItem(
///   thread: threadInfo,
///   isSelected: true,
///   hasActiveRun: false,
///   onTap: () => handleThreadSelection(threadInfo.id),
/// )
/// ```
class ThreadListItem extends StatelessWidget {
  /// Creates a thread list item.
  const ThreadListItem({
    required this.thread,
    required this.isSelected,
    required this.hasActiveRun,
    required this.onTap,
    super.key,
  });

  /// The thread information to display.
  final ThreadInfo thread;

  /// Whether this thread is currently selected.
  final bool isSelected;

  /// Whether this thread has an active run.
  final bool hasActiveRun;

  /// Callback when the item is tapped.
  final VoidCallback onTap;

  String _getTitle() {
    if (thread.hasName) {
      return thread.name;
    }
    return 'Thread ${getShortId(thread.id)}';
  }

  String _getSubtitle() {
    return formatRelativeTime(thread.updatedAt);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return ListTile(
      selected: isSelected,
      selectedTileColor: colorScheme.primaryContainer.withValues(alpha: 0.3),
      onTap: onTap,
      leading: hasActiveRun
          ? Semantics(
              label: 'Conversation in progress',
              child: SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: colorScheme.primary,
                ),
              ),
            )
          : Icon(
              Icons.chat_bubble_outline,
              color: isSelected ? colorScheme.primary : colorScheme.onSurface,
            ),
      title: Text(
        _getTitle(),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: theme.textTheme.bodyLarge?.copyWith(
          fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
          color: isSelected ? colorScheme.primary : null,
        ),
      ),
      subtitle: Text(
        _getSubtitle(),
        style: theme.textTheme.bodySmall?.copyWith(
          color: isSelected
              ? colorScheme.primary.withValues(alpha: 0.7)
              : colorScheme.onSurfaceVariant,
        ),
      ),
      trailing: isSelected
          ? ExcludeSemantics(
              child: Icon(
                Icons.check_circle,
                color: colorScheme.primary,
                size: 20,
              ),
            )
          : null,
    );
  }
}
