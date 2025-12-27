import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:soliplex_client/soliplex_client.dart';
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
            CompletedState(result: FailedResult(:final errorMessage)) =>
              ErrorDisplay(
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

    final thread = ref.read(currentThreadProvider);
    final selection = ref.read(threadSelectionProvider);

    // Create new thread if needed
    final ThreadInfo effectiveThread;
    if (thread == null || selection is NewThreadIntent) {
      final result = await _withErrorHandling(
        context,
        () => ref.read(apiProvider).createThread(room.id),
        'create thread',
      );
      switch (result) {
        case Ok(:final value):
          effectiveThread = value;
        case Err():
          return;
      }

      // Update selection to the new thread
      ref
          .read(threadSelectionProvider.notifier)
          .set(ThreadSelected(effectiveThread.id));

      // Persist last viewed and update URL
      await setLastViewedThread(
        roomId: room.id,
        threadId: effectiveThread.id,
        invalidate: invalidateLastViewed(ref),
      );
      if (context.mounted) {
        context.go('/rooms/${room.id}?thread=${effectiveThread.id}');
      }

      // Refresh threads list
      ref.invalidate(threadsProvider(room.id));
    } else {
      effectiveThread = thread;
    }

    // Start the run
    if (!context.mounted) return;
    await _withErrorHandling(
      context,
      () => ref.read(activeRunNotifierProvider.notifier).startRun(
            roomId: room.id,
            threadId: effectiveThread.id,
            userMessage: text,
            existingRunId: effectiveThread.initialRunId,
          ),
      'send message',
    );
  }

  /// Executes an async action with standardized error handling.
  ///
  /// Shows appropriate SnackBar messages for errors.
  /// Returns [Ok] with value on success, [Err] on error.
  Future<Result<T>> _withErrorHandling<T>(
    BuildContext context,
    Future<T> Function() action,
    String operation,
  ) async {
    try {
      return Ok(await action());
    } on NetworkException catch (e, stackTrace) {
      debugPrint('Failed to $operation: Network error - ${e.message}');
      debugPrint(stackTrace.toString());
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Network error: ${e.message}')),
        );
      }
      return Err('Network error: ${e.message}');
    } on AuthException catch (e, stackTrace) {
      debugPrint('Failed to $operation: Auth error - ${e.message}');
      debugPrint(stackTrace.toString());
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Authentication error: ${e.message}')),
        );
      }
      return Err('Authentication error: ${e.message}');
    } catch (e, stackTrace) {
      debugPrint('Failed to $operation: $e');
      debugPrint(stackTrace.toString());
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to $operation: $e')),
        );
      }
      return Err('$e');
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

// ---------------------------------------------------------------------------
// Result Type (private to this file)
// ---------------------------------------------------------------------------

/// Result type for operations that can succeed or fail.
sealed class _Result<T> {
  const _Result();
}

/// Successful result containing a value.
class Ok<T> extends _Result<T> {
  const Ok(this.value);
  final T value;
}

/// Failed result containing an error message.
class Err<T> extends _Result<T> {
  const Err(this.message);
  final String message;
}

/// Type alias for external pattern matching.
typedef Result<T> = _Result<T>;
