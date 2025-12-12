import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../client/client.dart';
import '../../providers/providers.dart';

/// Widget displaying thread history for the current room.
///
/// Shows a list of threads with options to create, select, and delete.
class HistoryWidget extends ConsumerWidget {
  const HistoryWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final roomId = ref.watch(currentRoomProvider);
    final currentThreadId = ref.watch(currentThreadProvider);

    if (roomId == null) {
      return const _EmptyHistory(
        message: 'Select a room to view threads',
      );
    }

    final threadsAsync = ref.watch(roomThreadsProvider(roomId));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _HistoryHeader(roomId: roomId),
        Expanded(
          child: threadsAsync.when(
            data: (threads) => threads.isEmpty
                ? const _EmptyHistory(message: 'No threads yet')
                : _ThreadList(
                    threads: threads,
                    selectedThreadId: currentThreadId,
                    onSelect: (threadId) {
                      ref.read(currentThreadProvider.notifier).state = threadId;
                    },
                    onDelete: (threadId) async {
                      final confirmed = await _showDeleteConfirmation(context);
                      if (confirmed) {
                        await ref.read(deleteThreadProvider)(roomId, threadId);
                        ref.invalidate(roomThreadsProvider(roomId));
                        if (currentThreadId == threadId) {
                          ref.read(currentThreadProvider.notifier).state = null;
                        }
                      }
                    },
                  ),
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => _EmptyHistory(
              message: 'Error: $error',
              isError: true,
            ),
          ),
        ),
      ],
    );
  }

  Future<bool> _showDeleteConfirmation(BuildContext context) async {
    return await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Delete Thread'),
            content: const Text(
              'Are you sure you want to delete this thread? This action cannot be undone.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Cancel'),
              ),
              TextButton(
                onPressed: () => Navigator.of(context).pop(true),
                style: TextButton.styleFrom(foregroundColor: Colors.red),
                child: const Text('Delete'),
              ),
            ],
          ),
        ) ??
        false;
  }
}

class _HistoryHeader extends ConsumerWidget {
  const _HistoryHeader({required this.roomId});

  final String roomId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).dividerColor,
          ),
        ),
      ),
      child: Row(
        children: [
          const Icon(Icons.history, size: 20),
          const SizedBox(width: 8),
          const Expanded(
            child: Text(
              'History',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 16,
              ),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'New Thread',
            onPressed: () async {
              final createThread = ref.read(createThreadProvider);
              final result = await createThread(roomId);
              ref.read(currentThreadProvider.notifier).state = result.threadId;
              ref.invalidate(roomThreadsProvider(roomId));
            },
            iconSize: 20,
            constraints: const BoxConstraints(
              minWidth: 32,
              minHeight: 32,
            ),
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
            onPressed: () => ref.invalidate(roomThreadsProvider(roomId)),
            iconSize: 20,
            constraints: const BoxConstraints(
              minWidth: 32,
              minHeight: 32,
            ),
          ),
        ],
      ),
    );
  }
}

class _ThreadList extends StatelessWidget {
  const _ThreadList({
    required this.threads,
    required this.selectedThreadId,
    required this.onSelect,
    required this.onDelete,
  });

  final List<ThreadInfo> threads;
  final String? selectedThreadId;
  final void Function(String) onSelect;
  final void Function(String) onDelete;

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      padding: const EdgeInsets.symmetric(vertical: 4),
      itemCount: threads.length,
      itemBuilder: (context, index) {
        final thread = threads[index];
        final isSelected = thread.id == selectedThreadId;
        return _ThreadCard(
          thread: thread,
          isSelected: isSelected,
          onTap: () => onSelect(thread.id),
          onDelete: () => onDelete(thread.id),
        );
      },
    );
  }
}

class _ThreadCard extends StatelessWidget {
  const _ThreadCard({
    required this.thread,
    required this.isSelected,
    required this.onTap,
    required this.onDelete,
  });

  final ThreadInfo thread;
  final bool isSelected;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      child: Card(
        elevation: isSelected ? 2 : 0,
        color: isSelected
            ? theme.colorScheme.primaryContainer
            : theme.colorScheme.surface,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        thread.name ?? 'Unnamed Thread',
                        style: TextStyle(
                          fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                          color: isSelected
                              ? theme.colorScheme.onPrimaryContainer
                              : null,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.delete_outline, size: 18),
                      onPressed: onDelete,
                      tooltip: 'Delete',
                      constraints: const BoxConstraints(
                        minWidth: 28,
                        minHeight: 28,
                      ),
                      padding: EdgeInsets.zero,
                      iconSize: 18,
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Icon(
                      Icons.access_time,
                      size: 12,
                      color: theme.colorScheme.outline,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      _formatDate(thread.createdAt),
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.outline,
                      ),
                    ),
                    if (thread.description != null) ...[
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          thread.description!,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.outline,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _formatDate(DateTime? date) {
    if (date == null) return 'Unknown';
    final now = DateTime.now();
    final diff = now.difference(date);

    if (diff.inDays == 0) {
      if (diff.inHours == 0) {
        if (diff.inMinutes == 0) {
          return 'Just now';
        }
        return '${diff.inMinutes}m ago';
      }
      return '${diff.inHours}h ago';
    } else if (diff.inDays < 7) {
      return '${diff.inDays}d ago';
    } else {
      return '${date.month}/${date.day}/${date.year}';
    }
  }
}

class _EmptyHistory extends StatelessWidget {
  const _EmptyHistory({
    required this.message,
    this.isError = false,
  });

  final String message;
  final bool isError;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              isError ? Icons.error_outline : Icons.forum_outlined,
              size: 48,
              color: isError ? Colors.red : Theme.of(context).colorScheme.outline,
            ),
            const SizedBox(height: 12),
            Text(
              message,
              style: TextStyle(
                color: isError ? Colors.red : Theme.of(context).colorScheme.outline,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
