import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';
import 'package:soliplex_frontend/shared/utils/date_formatter.dart';
import 'package:soliplex_frontend/shared/widgets/empty_state.dart';
import 'package:soliplex_frontend/shared/widgets/error_display.dart';
import 'package:soliplex_frontend/shared/widgets/loading_indicator.dart';

/// Screen displaying threads within a specific room.
class RoomScreen extends ConsumerWidget {
  const RoomScreen({
    required this.roomId,
    super.key,
  });

  final String roomId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final room = ref.watch(currentRoomProvider);
    final threadsAsync = ref.watch(threadsProvider(roomId));

    return Scaffold(
      appBar: AppBar(
        title: Text(room?.name ?? 'Room'),
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
                title: Text(thread.name ?? 'Thread ${thread.id}'),
                subtitle: Text(
                  switch (thread.createdAt) {
                    final createdAt? =>
                      'Created ${formatRelativeTime(createdAt)}',
                    null => 'No date',
                  },
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  ref.read(threadSelectionProvider.notifier)
                      .set(ThreadSelected(thread.id));
                  context.push('/rooms/$roomId/thread/${thread.id}');
                },
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
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          // Set new thread intent and navigate to thread screen
          // The ChatPanel will create the thread when first message is sent
          ref
              .read(threadSelectionProvider.notifier)
              .set(const NewThreadIntent());
          context.push('/rooms/$roomId/thread/new');
        },
        child: const Icon(Icons.add),
      ),
    );
  }
}
