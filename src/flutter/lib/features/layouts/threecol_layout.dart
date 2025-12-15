import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/network/connection_manager.dart';
import 'package:soliplex/core/providers/app_providers.dart';
import 'package:soliplex/core/services/thread_history_service.dart';
import 'package:soliplex/features/chat/chat_content.dart';
import 'package:soliplex/features/context/context_pane.dart';

/// Three-column layout - Thread history | Chat | Context pane.
///
/// Left: Thread history for conversation management
/// Middle: Chat conversation
/// Right: Context pane showing state and tool results
class ThreeColumnLayout extends ConsumerWidget {
  const ThreeColumnLayout({super.key, this.roomId});
  final String? roomId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Row(
      children: [
        // Thread history (left column)
        SizedBox(
          width: 250,
          child: ColoredBox(
            color: Theme.of(context).colorScheme.surfaceContainerLow,
            child: _ThreadHistoryPane(roomId: roomId),
          ),
        ),
        const VerticalDivider(width: 1),
        // Chat (middle column - flexible) - ClipRect prevents overflow during
        // scroll
        Expanded(
          child: ClipRect(child: ChatContent(roomId: roomId)),
        ),
        const VerticalDivider(width: 1),
        // Context pane (right column)
        SizedBox(
          width: 300,
          child: ColoredBox(
            color: Theme.of(context).colorScheme.surfaceContainerLow,
            child: ContextPane(roomId: roomId),
          ),
        ),
      ],
    );
  }
}

/// Thread history pane that fetches and displays threads from the API.
class _ThreadHistoryPane extends ConsumerStatefulWidget {
  const _ThreadHistoryPane({this.roomId});
  final String? roomId;

  @override
  ConsumerState<_ThreadHistoryPane> createState() => _ThreadHistoryPaneState();
}

class _ThreadHistoryPaneState extends ConsumerState<_ThreadHistoryPane> {
  @override
  void initState() {
    super.initState();
    // Fetch threads when pane is first shown
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _fetchThreads();
    });
  }

  @override
  void didUpdateWidget(_ThreadHistoryPane oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.roomId != widget.roomId) {
      _fetchThreads();
    }
  }

  void _fetchThreads() {
    final connectionManager = ref.read(connectionManagerProvider);
    final serverId = connectionManager.activeServerId;
    final roomId = widget.roomId;
    if (serverId != null && roomId != null) {
      final params = (serverId: serverId, roomId: roomId);
      ref.read(threadHistoryProvider(params).notifier).fetchThreads();
    }
  }

  @override
  Widget build(BuildContext context) {
    final server = ref.watch(currentServerFromAppStateProvider);
    final roomId = widget.roomId;
    final connectionManager = ref.watch(connectionManagerProvider);

    // If no server or room, show placeholder
    if (server == null || roomId == null) {
      return const Center(child: Text('Select a room'));
    }

    // Get messages from ConnectionManager
    final messages = connectionManager.getMessages(roomId);
    final session = connectionManager.getSession(roomId);
    final currentThreadId = session.connectionInfo.threadId;

    // Use ConnectionManager's server ID (URL-derived, not UUID)
    final serverId = connectionManager.activeServerId;
    if (serverId == null) {
      return const Center(child: Text('Connecting...'));
    }
    final params = (serverId: serverId, roomId: roomId);
    final threadState = ref.watch(threadHistoryProvider(params));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Text('Threads', style: Theme.of(context).textTheme.titleSmall),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.refresh, size: 20),
                tooltip: 'Refresh threads',
                onPressed: _fetchThreads,
              ),
              IconButton(
                icon: const Icon(Icons.add, size: 20),
                tooltip: 'New thread',
                onPressed: () {
                  // Clear current conversation to start new
                  connectionManager.clearMessages(roomId);
                  connectionManager.disposeSession(roomId);
                  ref
                      .read(threadHistoryProvider(params).notifier)
                      .selectThread(null);
                },
              ),
            ],
          ),
        ),
        const Divider(height: 1),

        // Current session card - show when:
        // 1. We have messages AND
        // 2. Either no thread selected, OR current threadId is not in the
        // fetched list
        if (messages.isNotEmpty) ...[
          Builder(
            builder: (context) {
              final isInList =
                  currentThreadId != null &&
                  threadState.threads.any((t) => t.threadId == currentThreadId);

              // Only show if this is a new thread not yet in the list
              if (currentThreadId == null || !isInList) {
                return Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  child: Card(
                    color: Theme.of(context).colorScheme.primaryContainer,
                    child: ListTile(
                      leading: const Icon(Icons.chat_bubble),
                      title: const Text('Current Session'),
                      subtitle: Text('${messages.length} messages'),
                      trailing: currentThreadId != null
                          ? const Icon(Icons.cloud_done, size: 16)
                          : const Icon(Icons.cloud_off, size: 16),
                      onTap: currentThreadId != null
                          ? () {
                              // Select this thread
                              ref
                                  .read(threadHistoryProvider(params).notifier)
                                  .selectThread(currentThreadId);
                            }
                          : null,
                    ),
                  ),
                );
              }
              return const SizedBox.shrink();
            },
          ),
        ],

        // Thread list
        Expanded(
          child: threadState.isLoading
              ? const Center(child: CircularProgressIndicator())
              : threadState.error != null
              ? _buildErrorState(context, threadState.error!)
              : threadState.threads.isEmpty
              ? _buildEmptyState(context)
              : _buildThreadList(context, ref, threadState, params, roomId),
        ),
      ],
    );
  }

  Widget _buildErrorState(BuildContext context, String error) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.error_outline,
              size: 48,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: 8),
            Text(
              'Error loading threads',
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
            const SizedBox(height: 4),
            Text(
              error,
              style: Theme.of(context).textTheme.bodySmall,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            TextButton.icon(
              onPressed: _fetchThreads,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.forum_outlined,
            size: 48,
            color: Theme.of(context).colorScheme.outline,
          ),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Text(
              'This is where current and past threads will be listed',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.outline,
              ),
              textAlign: TextAlign.center,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildThreadList(
    BuildContext context,
    WidgetRef ref,
    ThreadHistoryState threadState,
    ({String serverId, String roomId}) params,
    String roomId,
  ) {
    final connectionManager = ref.watch(connectionManagerProvider);
    final session = connectionManager.getSession(roomId);
    final activeThreadId = session.connectionInfo.threadId;

    return ListView.builder(
      padding: const EdgeInsets.symmetric(vertical: 4),
      itemCount: threadState.threads.length,
      itemBuilder: (context, index) {
        final thread = threadState.threads[index];
        // Highlight if this is the active thread
        final isSelected = thread.threadId == activeThreadId;

        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
          child: Card(
            color: isSelected
                ? Theme.of(context).colorScheme.primaryContainer
                : null,
            child: ListTile(
              leading: Icon(
                Icons.chat_bubble_outline,
                color: isSelected
                    ? Theme.of(context).colorScheme.onPrimaryContainer
                    : null,
              ),
              title: Text(
                thread.title ?? 'Thread ${thread.threadId.substring(0, 8)}...',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: isSelected
                    ? TextStyle(
                        color: Theme.of(context).colorScheme.onPrimaryContainer,
                      )
                    : null,
              ),
              subtitle: Text(
                _formatDate(thread.createdAt),
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: isSelected
                      ? Theme.of(
                          context,
                        ).colorScheme.onPrimaryContainer.withValues(alpha: 0.7)
                      : null,
                ),
              ),
              onTap: () async {
                // Select thread in history
                ref
                    .read(threadHistoryProvider(params).notifier)
                    .selectThread(thread.threadId);

                // Clear current messages
                connectionManager.clearMessages(roomId);

                // TODO(dev): Load thread history from server
                // For now, thread switching is a placeholder - the session
                // would need to be reinitialized with the selected thread
              },
            ),
          ),
        );
      },
    );
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final diff = now.difference(date);

    if (diff.inDays == 0) {
      // ignore: lines_longer_than_80_chars (auto-documented)
      return 'Today ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
    } else if (diff.inDays == 1) {
      return 'Yesterday';
    } else if (diff.inDays < 7) {
      return '${diff.inDays} days ago';
    } else {
      return '${date.month}/${date.day}/${date.year}';
    }
  }
}
