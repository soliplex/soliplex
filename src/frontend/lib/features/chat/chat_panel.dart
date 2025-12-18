import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_frontend/core/models/active_run_state.dart';
import 'package:soliplex_frontend/core/providers/active_run_provider.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';
import 'package:soliplex_frontend/features/chat/widgets/chat_input.dart';
import 'package:soliplex_frontend/features/chat/widgets/message_list.dart';
import 'package:soliplex_frontend/shared/widgets/error_display.dart';

/// Main chat panel that combines message list and input.
///
/// This panel:
/// - Displays messages from the current thread
/// - Provides input for sending new messages
/// - Handles thread creation for new conversations
/// - Shows cancel button during streaming
/// - Handles errors with ErrorDisplay
///
/// The panel integrates with:
/// - [currentThreadProvider] for the active thread
/// - [activeRunNotifierProvider] for streaming state
/// - [threadSelectionProvider] for thread selection state
///
/// Example:
/// ```dart
/// ChatPanel()
/// ```
class ChatPanel extends ConsumerWidget {
  /// Creates a chat panel.
  const ChatPanel({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final runState = ref.watch(activeRunNotifierProvider);

    return Column(
      children: [
        // App bar with cancel button
        if (runState.isRunning)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              border: Border(
                bottom: BorderSide(
                  color: Theme.of(context).colorScheme.outlineVariant,
                ),
              ),
            ),
            child: Row(
              children: [
                const Expanded(
                  child: Text('Streaming response...'),
                ),
                TextButton.icon(
                  onPressed: () => _handleCancel(ref),
                  icon: const Icon(Icons.cancel),
                  label: const Text('Cancel'),
                ),
              ],
            ),
          ),

        // Message list
        Expanded(
          child: switch (runState) {
            CompletedState(result: Failed(:final errorMessage)) => ErrorDisplay(
                error: errorMessage,
                onRetry: () => _handleRetry(ref),
              ),
            _ => const MessageList(),
          },
        ),

        // Input
        ChatInput(
          onSend: (text) => _handleSend(context, ref, text),
        ),
      ],
    );
  }

  /// Handles sending a message.
  Future<void> _handleSend(
    BuildContext context,
    WidgetRef ref,
    String text,
  ) async {
    final room = ref.read(currentRoomProvider);
    if (room == null) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No room selected')),
        );
      }
      return;
    }

    var thread = ref.read(currentThreadProvider);
    final selection = ref.read(threadSelectionProvider);

    // Create new thread if needed
    if (thread == null || selection is NewThreadIntent) {
      try {
        final api = ref.read(apiProvider);
        final newThread = await api.createThread(room.id);
        thread = newThread;

        // Update selection to the new thread
        ref.read(threadSelectionProvider.notifier)
            .set(ThreadSelected(newThread.id));

        // Refresh threads list
        ref.invalidate(threadsProvider(room.id));
      } catch (e) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Failed to create thread: $e')),
          );
        }
        return;
      }
    }

    // Start the run
    try {
      await ref.read(activeRunNotifierProvider.notifier).startRun(
            roomId: room.id,
            threadId: thread.id,
            userMessage: text,
          );
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to send message: $e')),
        );
      }
    }
  }

  /// Handles cancelling the active run.
  Future<void> _handleCancel(WidgetRef ref) async {
    await ref.read(activeRunNotifierProvider.notifier).cancelRun();
  }

  /// Handles retrying after an error.
  void _handleRetry(WidgetRef ref) {
    ref.read(activeRunNotifierProvider.notifier).reset();
  }
}
