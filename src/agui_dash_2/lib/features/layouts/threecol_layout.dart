import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/services/agui_service.dart';
import '../../core/services/chat_service.dart';
import '../../core/services/thread_history_service.dart';
import '../chat/chat_content.dart';
import '../context/context_pane.dart';

/// Three-column layout - Thread history | Chat | Context pane.
///
/// Left: Thread history for conversation management
/// Middle: Chat conversation
/// Right: Context pane showing state and tool results
class ThreeColumnLayout extends ConsumerWidget {
  const ThreeColumnLayout({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Row(
      children: [
        // Thread history (left column)
        SizedBox(
          width: 250,
          child: Container(
            color: Theme.of(context).colorScheme.surfaceContainerLow,
            child: const _ThreadHistoryPane(),
          ),
        ),
        const VerticalDivider(width: 1),
        // Chat (middle column - flexible) - ClipRect prevents overflow during scroll
        const Expanded(child: ClipRect(child: ChatContent())),
        const VerticalDivider(width: 1),
        // Context pane (right column)
        SizedBox(
          width: 300,
          child: Container(
            color: Theme.of(context).colorScheme.surfaceContainerLow,
            child: const ContextPane(),
          ),
        ),
      ],
    );
  }
}

/// Thread history pane that fetches and displays threads from the API.
class _ThreadHistoryPane extends ConsumerStatefulWidget {
  const _ThreadHistoryPane();

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

  void _fetchThreads() {
    final config = ref.read(agUiConfigProvider);
    if (config != null) {
      final params = (baseUrl: config.baseUrl, roomId: config.roomId);
      ref.read(threadHistoryProvider(params).notifier).fetchThreads();
    }
  }

  @override
  Widget build(BuildContext context) {
    final config = ref.watch(agUiConfigProvider);
    final chatState = ref.watch(chatProvider);
    final agUiService = ref.watch(agUiServiceProvider);

    // If no config, show placeholder
    if (config == null) {
      return const Center(child: Text('Select a room'));
    }

    final params = (baseUrl: config.baseUrl, roomId: config.roomId);
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
                  ref.read(chatProvider.notifier).clearMessages();
                  ref.read(agUiServiceProvider).resetConversation();
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
        // 2. Either no thread selected, OR current threadId is not in the fetched list
        if (chatState.messages.isNotEmpty) ...[
          Builder(builder: (context) {
            final currentThreadId = agUiService.threadId;
            final isInList = currentThreadId != null &&
                threadState.threads.any((t) => t.threadId == currentThreadId);
            final isSelected = threadState.selectedThreadId == currentThreadId;

            // Only show if this is a new thread not yet in the list
            if (currentThreadId == null || !isInList) {
              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                child: Card(
                  color: Theme.of(context).colorScheme.primaryContainer,
                  child: ListTile(
                    leading: const Icon(Icons.chat_bubble),
                    title: const Text('Current Session'),
                    subtitle: Text('${chatState.messages.length} messages'),
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
          }),
        ],

        // Thread list
        Expanded(
          child: threadState.isLoading
              ? const Center(child: CircularProgressIndicator())
              : threadState.error != null
              ? _buildErrorState(context, threadState.error!)
              : threadState.threads.isEmpty
              ? _buildEmptyState(context)
              : _buildThreadList(context, ref, threadState, params),
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
          Text(
            'No threads yet',
            style: TextStyle(color: Theme.of(context).colorScheme.outline),
          ),
          const SizedBox(height: 4),
          Text(
            'Start a conversation',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.outline,
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
    ({String baseUrl, String roomId}) params,
  ) {
    final agUiService = ref.watch(agUiServiceProvider);
    final activeThreadId = agUiService.threadId;

    return ListView.builder(
      padding: const EdgeInsets.symmetric(vertical: 4),
      itemCount: threadState.threads.length,
      itemBuilder: (context, index) {
        final thread = threadState.threads[index];
        // Highlight if this is the active thread (from AgUiService)
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
                        ).colorScheme.onPrimaryContainer.withOpacity(0.7)
                      : null,
                ),
              ),
              onTap: () async {
                // Select thread in history
                ref
                    .read(threadHistoryProvider(params).notifier)
                    .selectThread(thread.threadId);

                // Clear current chat messages
                ref.read(chatProvider.notifier).clearMessages();

                // Resume the thread and load history
                final messages = await ref
                    .read(agUiServiceProvider)
                    .resumeThread(thread.threadId);

                // Load the historical messages into chat
                if (messages.isNotEmpty) {
                  ref.read(chatProvider.notifier).loadMessages(messages);
                }
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
