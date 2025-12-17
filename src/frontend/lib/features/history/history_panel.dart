import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
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

        // Auto-select first thread if none selected
        final currentThreadId = ref.watch(currentThreadIdProvider);
        if (currentThreadId == null) {
          // Use addPostFrameCallback to avoid setState during build
          WidgetsBinding.instance.addPostFrameCallback((_) {
            ref.read(currentThreadIdProvider.notifier).state = threads.first.id;
            // Clear new thread intent since we have an existing thread
            ref.read(newThreadIntentProvider.notifier).state = false;
          });
        }

        // Get active run state to show indicators
        final activeRunState = ref.watch(activeRunNotifierProvider);
        final activeThreadId = activeRunState.threadId;

        return Column(
          children: [
            NewConversationButton(
              onPressed: () => _handleNewConversation(ref),
            ),
            const Divider(height: 1),
            Expanded(
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
                    onTap: () => _handleThreadSelection(ref, thread.id),
                  );
                },
              ),
            ),
          ],
        );
      },
      onRetry: () => ref.refresh(threadsProvider(roomId)),
    );
  }

  /// Handles selection of a thread.
  ///
  /// Updates the current thread ID and clears the new thread intent.
  void _handleThreadSelection(WidgetRef ref, String threadId) {
    ref.read(currentThreadIdProvider.notifier).state = threadId;
    ref.read(newThreadIntentProvider.notifier).state = false;
  }

  /// Handles the "New Conversation" button press.
  ///
  /// Clears the current thread selection and sets the new thread intent flag.
  /// This signals to the chat input that the next message should create a
  /// new thread.
  void _handleNewConversation(WidgetRef ref) {
    ref.read(currentThreadIdProvider.notifier).state = null;
    ref.read(newThreadIntentProvider.notifier).state = true;
  }
}
