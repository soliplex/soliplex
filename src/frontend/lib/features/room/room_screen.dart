import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:soliplex_frontend/core/constants/breakpoints.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';
import 'package:soliplex_frontend/features/chat/chat_panel.dart';
import 'package:soliplex_frontend/features/history/history_panel.dart';
import 'package:soliplex_frontend/shared/widgets/app_shell.dart';
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
  String? _initializedForRoomId;
  bool _sidebarCollapsed = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initializeThreadSelection();
    });
  }

  @override
  void didUpdateWidget(RoomScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.roomId != widget.roomId) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _initializeThreadSelection();
      });
    }
  }

  /// Initializes thread selection with fallback chain.
  ///
  /// Priority: query param → last viewed → first thread.
  Future<void> _initializeThreadSelection() async {
    if (_initializedForRoomId == widget.roomId) return;
    _initializedForRoomId = widget.roomId;

    // Sync global room ID for currentRoomProvider and currentThreadProvider
    ref.read(currentRoomIdProvider.notifier).set(widget.roomId);

    final threads = await ref.read(threadsProvider(widget.roomId).future);
    if (!mounted) return;

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
    if (!mounted) return;

    if (lastViewed case HasLastViewed(:final threadId)
        when threads.any((t) => t.id == threadId)) {
      ref.read(threadSelectionProvider.notifier).set(ThreadSelected(threadId));
      return;
    }

    // 3. First thread
    _selectThread(threads.first.id);
  }

  /// Selects a thread and persists as last viewed.
  void _selectThread(String threadId) {
    selectAndPersistThread(
      ref: ref,
      roomId: widget.roomId,
      threadId: threadId,
    );
  }

  /// Sidebar width for desktop layout.
  static const double _sidebarWidth = 300;

  @override
  Widget build(BuildContext context) {
    final isDesktop = MediaQuery.of(context).size.width >= kDesktopBreakpoint;

    return AppShell(
      config: ShellConfig(
        leading: isDesktop ? _buildSidebarToggle() : null,
        title: _buildRoomDropdown(),
        drawer: isDesktop ? null : HistoryPanel(roomId: widget.roomId),
        floatingActionButton: Semantics(
          label: 'Create new thread',
          child: FloatingActionButton(
            tooltip: 'Create new thread',
            onPressed: _handleNewThread,
            child: const Icon(Icons.add),
          ),
        ),
      ),
      body: isDesktop ? _buildDesktopLayout(context) : const ChatPanel(),
    );
  }

  Widget _buildSidebarToggle() {
    return Semantics(
      label: _sidebarCollapsed
          ? 'Show thread list sidebar'
          : 'Hide thread list sidebar',
      child: IconButton(
        icon: Icon(_sidebarCollapsed ? Icons.menu : Icons.menu_open),
        tooltip: _sidebarCollapsed ? 'Show threads' : 'Hide threads',
        onPressed: () => setState(() => _sidebarCollapsed = !_sidebarCollapsed),
      ),
    );
  }

  Widget _buildRoomDropdown() {
    final roomsAsync = ref.watch(roomsProvider);
    final currentRoom = ref.watch(currentRoomProvider);

    return roomsAsync.when(
      data: (rooms) => Semantics(
        label: 'Room selector, current: ${currentRoom?.name ?? 'none'}',
        child: Tooltip(
          message: 'Switch to another room',
          child: DropdownMenu<String>(
            initialSelection: currentRoom?.id,
            dropdownMenuEntries: rooms
                .map((r) => DropdownMenuEntry(value: r.id, label: r.name))
                .toList(),
            onSelected: (id) {
              if (id != null) context.go('/rooms/$id');
            },
          ),
        ),
      ),
      loading: () => Semantics(
        label: 'Loading rooms',
        child: const SizedBox(
          width: 24,
          height: 24,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      ),
      error: (error, stackTrace) {
        debugPrint('Failed to load rooms: $error');
        debugPrint(stackTrace.toString());
        return Semantics(
          label: 'Error loading rooms',
          child: const Tooltip(
            message: 'Failed to load rooms',
            child: Icon(Icons.error_outline),
          ),
        );
      },
    );
  }

  Widget _buildDesktopLayout(BuildContext context) {
    return Row(
      children: [
        if (!_sidebarCollapsed)
          SizedBox(
            width: _sidebarWidth,
            child: DecoratedBox(
              decoration: BoxDecoration(
                border: Border(
                  right: BorderSide(
                    color: Theme.of(context).colorScheme.outlineVariant,
                  ),
                ),
              ),
              child: HistoryPanel(roomId: widget.roomId),
            ),
          ),
        const Expanded(child: ChatPanel()),
      ],
    );
  }

  void _handleNewThread() {
    ref.read(threadSelectionProvider.notifier).set(const NewThreadIntent());
    // ChatPanel will create thread on first message
  }
}
