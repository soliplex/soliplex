import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';
import 'package:soliplex_frontend/shared/utils/date_formatter.dart';
import 'package:soliplex_frontend/shared/widgets/app_shell.dart';
import 'package:soliplex_frontend/shared/widgets/empty_state.dart';
import 'package:soliplex_frontend/shared/widgets/error_display.dart';
import 'package:soliplex_frontend/shared/widgets/loading_indicator.dart';
import 'package:soliplex_frontend/shared/widgets/shell_config.dart';

/// Screen displaying threads within a specific room.
///
/// Implements async thread selection on mount:
/// 1. Query param (`initialThreadId`) if valid
/// 2. Last viewed thread from SharedPreferences if valid
/// 3. First thread in list
///
/// This is a dynamic screen that builds its own AppShell to provide
/// dynamic ShellConfig (room name in title, sidebar toggle, room dropdown).
class RoomScreen extends ConsumerStatefulWidget {
  const RoomScreen({
    required this.roomId,
    this.initialThreadId,
    super.key,
  });

  final String roomId;

  /// Thread ID from query param (?thread=xyz). Used for deep linking.
  final String? initialThreadId;

  @override
  ConsumerState<RoomScreen> createState() => _RoomScreenState();
}

class _RoomScreenState extends ConsumerState<RoomScreen> {
  bool _initialized = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initializeThreadSelection();
    });
  }

  /// Initializes thread selection with fallback chain.
  ///
  /// Priority: query param → last viewed → first thread.
  Future<void> _initializeThreadSelection() async {
    if (_initialized) return;
    _initialized = true;

    final threads = await ref.read(threadsProvider(widget.roomId).future);
    if (threads.isEmpty) {
      ref.read(threadSelectionProvider.notifier).set(const NoThreadSelected());
      return;
    }

    // 1. Query param (if valid)
    if (widget.initialThreadId != null &&
        threads.any((t) => t.id == widget.initialThreadId)) {
      _selectThread(widget.initialThreadId!);
      return;
    }

    // 2. Last viewed (if valid)
    final lastViewed =
        await ref.read(lastViewedThreadProvider(widget.roomId).future);
    if (lastViewed != null && threads.any((t) => t.id == lastViewed)) {
      ref
          .read(threadSelectionProvider.notifier)
          .set(ThreadSelected(lastViewed));
      return;
    }

    // 3. First thread
    _selectThread(threads.first.id);
  }

  /// Selects a thread and persists as last viewed.
  void _selectThread(String threadId) {
    ref.read(threadSelectionProvider.notifier).set(ThreadSelected(threadId));
    unawaited(
      setLastViewedThread(
        roomId: widget.roomId,
        threadId: threadId,
        invalidate: invalidateLastViewed(ref),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final room = ref.watch(currentRoomProvider);
    final threadsAsync = ref.watch(threadsProvider(widget.roomId));

    return AppShell(
      config: ShellConfig(
        title: Text(room?.name ?? 'Room'),
        floatingActionButton: FloatingActionButton(
          tooltip: 'Create new thread',
          onPressed: _handleNewThread,
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
                onTap: () => _handleThreadSelection(thread.id),
              );
            },
          );
        },
        loading: () => const LoadingIndicator(message: 'Loading threads...'),
        error: (error, stack) => ErrorDisplay(
          error: error,
          onRetry: () => ref.invalidate(threadsProvider(widget.roomId)),
        ),
      ),
    );
  }

  void _handleThreadSelection(String threadId) {
    _selectThread(threadId);
    context.go('/rooms/${widget.roomId}?thread=$threadId');
  }

  void _handleNewThread() {
    ref.read(threadSelectionProvider.notifier).set(const NewThreadIntent());
    // ChatPanel will create thread on first message
  }
}
