import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:soliplex_frontend/core/models/active_run_state.dart';
import 'package:soliplex_frontend/core/providers/active_run_provider.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';
import 'package:soliplex_frontend/features/history/widgets/new_conversation_button.dart';
import 'package:soliplex_frontend/features/history/widgets/thread_list_item.dart';
import 'package:soliplex_frontend/shared/widgets/async_value_handler.dart';
import 'package:soliplex_frontend/shared/widgets/empty_state.dart';

/// The history panel displays a list of conversation threads for the
/// current room.
///
/// Features:
/// - "New Conversation" button at the top
/// - List of threads sorted by most recent
/// - Highlights currently selected thread
/// - Shows activity indicator for threads with active runs
/// - Auto-selection of first thread when none selected
/// - Loading, error, and empty states
///
/// This panel is designed to be displayed in a sidebar or drawer for
/// desktop/tablet layouts.
///
/// Example usage:
/// ```dart
/// Scaffold(
///   body: Row(
///     children: [
///       SizedBox(
///         width: 300,
///         child: HistoryPanel(),
///       ),
///       Expanded(child: ChatPanel()),
///     ],
///   ),
/// )
/// ```
class HistoryPanel extends ConsumerWidget {
  /// Creates a history panel.
  const HistoryPanel({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Get current room ID
    final roomId = ref.watch(currentRoomIdProvider);

    if (roomId == null) {
      return const EmptyState(
        message: 'Select a room to view conversations',
        icon: Icons.forum_outlined,
      );
    }

    // Watch threads for this room
    final threadsAsync = ref.watch(threadsProvider(roomId));

    return AsyncValueHandler(
      value: threadsAsync,
      data: (threads) {
        // Empty state - no threads yet
        if (threads.isEmpty) {
          return Column(
            children: [
              NewConversationButton(
                onPressed: () => _handleNewConversation(ref),
              ),
              const Expanded(
                child: EmptyState(
                  message: 'No conversations yet\nStart a new one!',
                  icon: Icons.chat_bubble_outline,
                ),
              ),
            ],
          );
        }

        // Get active run state to show indicators
        final activeRunState = ref.watch(activeRunNotifierProvider);
        // Extract threadId from running state (only RunningState has threadId)
        final activeThreadId = switch (activeRunState) {
          RunningState(:final threadId) => threadId,
          _ => null,
        };
        final currentThreadId = ref.watch(currentThreadIdProvider);

        return Column(
          children: [
            NewConversationButton(
              onPressed: () => _handleNewConversation(ref),
            ),
            const Divider(height: 1),
            Expanded(
              child: RefreshIndicator(
                onRefresh: () async {
                  ref.invalidate(threadsProvider(roomId));
                  // Wait for the provider to reload
                  await ref.read(threadsProvider(roomId).future);
                },
                child: ListView.builder(
                  itemCount: threads.length,
                  itemBuilder: (context, index) {
                    final thread = threads[index];
                    final isSelected = thread.id == currentThreadId;
                    final hasActiveRun =
                        activeThreadId != null && activeThreadId == thread.id;

                    return ThreadListItem(
                      thread: thread,
                      isSelected: isSelected,
                      hasActiveRun: hasActiveRun,
                      onTap: () => _handleThreadSelection(
                        context,
                        ref,
                        roomId,
                        thread.id,
                      ),
                    );
                  },
                ),
              ),
            ),
          ],
        );
      },
      onRetry: () => ref.refresh(threadsProvider(roomId)),
    );
  }

  /// Handles selection of a thread.
  void _handleThreadSelection(
    BuildContext context,
    WidgetRef ref,
    String roomId,
    String threadId,
  ) {
    selectThread(
      ref: ref,
      roomId: roomId,
      threadId: threadId,
      navigate: context.go,
    );
  }

  /// Handles the "New Conversation" button press.
  ///
  /// Sets the selection to [NewThreadIntent], signaling that the next
  /// message should create a new thread.
  void _handleNewConversation(WidgetRef ref) {
    ref.read(threadSelectionProvider.notifier).set(const NewThreadIntent());
  }
}
