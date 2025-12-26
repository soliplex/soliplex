import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';
import 'package:soliplex_frontend/shared/utils/date_formatter.dart';
import 'package:soliplex_frontend/shared/widgets/app_bar_config.dart';
import 'package:soliplex_frontend/shared/widgets/app_shell.dart';
import 'package:soliplex_frontend/shared/widgets/empty_state.dart';
import 'package:soliplex_frontend/shared/widgets/error_display.dart';
import 'package:soliplex_frontend/shared/widgets/loading_indicator.dart';

/// Screen displaying threads within a specific room.
///
/// When [initialThreadId] is provided (from query param), the screen
/// will select that thread. Otherwise, it falls back to last viewed
/// or first thread.
///
/// This is a dynamic screen that builds its own AppShell to provide
/// dynamic AppBarConfig (room name in title, future: room dropdown,
/// sidebar toggle).
class RoomScreen extends ConsumerWidget {
  const RoomScreen({
    required this.roomId,
    this.initialThreadId,
    super.key,
  });

  final String roomId;

  /// Thread ID from query param (?thread=xyz). Used for deep linking.
  // TODO(Phase3): Use initialThreadId in async thread selection flow
  final String? initialThreadId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final room = ref.watch(currentRoomProvider);
    final threadsAsync = ref.watch(threadsProvider(roomId));

    return AppShell(
      config: AppBarConfig(
        title: Text(room?.name ?? 'Room'),
        floatingActionButton: FloatingActionButton(
          tooltip: 'Create new thread',
          onPressed: () => _handleNewThread(context, ref),
          child: const Icon(Icons.add),
        ),
      ),
      body: threadsAsync.when(
        data: (threads) {
          if (threads.isEmpty) {
            return const EmptyState(
              message: 'No threads in this room',
              icon: Icons.chat_bubble_outline,
            );
          }

          return ListView.builder(
            itemCount: threads.length,
            itemBuilder: (context, index) {
              final thread = threads[index];
              return ListTile(
                leading: const Icon(Icons.chat),
                title: Text(
                  thread.hasName ? thread.name : 'Thread ${thread.id}',
                ),
                subtitle: Text(
                  'Created ${formatRelativeTime(thread.createdAt)}',
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => _handleThreadSelection(context, ref, thread.id),
              );
            },
          );
        },
        loading: () => const LoadingIndicator(message: 'Loading threads...'),
        error: (error, stack) => ErrorDisplay(
          error: error,
          onRetry: () => ref.invalidate(threadsProvider(roomId)),
        ),
      ),
    );
  }

  void _handleThreadSelection(
    BuildContext context,
    WidgetRef ref,
    String threadId,
  ) {
    ref.read(threadSelectionProvider.notifier).set(ThreadSelected(threadId));
    // Use query param format directly (not old path that triggers redirect)
    context.go('/rooms/$roomId?thread=$threadId');
  }

  void _handleNewThread(BuildContext context, WidgetRef ref) {
    ref.read(threadSelectionProvider.notifier).set(const NewThreadIntent());
    // Stay on room screen - ChatPanel will create thread on first message
    // No navigation needed since we're already on RoomScreen
  }
}
