import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';
import 'package:soliplex_frontend/features/chat/chat_panel.dart';
import 'package:soliplex_frontend/features/history/history_panel.dart';
import 'package:soliplex_frontend/features/inspector/http_inspector_panel.dart';

/// Thread screen with chat and history panels.
///
/// Layout:
/// - **Desktop (>600px)**: Side-by-side History (left) + Chat (right)
/// - **Mobile (<600px)**: Chat only (History accessed via navigation)
///
/// Updates providers on mount:
/// - Sets [currentRoomIdProvider] to the provided roomId
/// - Sets [threadSelectionProvider] based on threadId:
///   - If threadId is 'new', sets [NewThreadIntent]
///   - Otherwise, sets [ThreadSelected] with the threadId
///
/// Example:
/// ```dart
/// ThreadScreen(
///   roomId: 'room-123',
///   threadId: 'thread-456',
/// )
/// ```
class ThreadScreen extends ConsumerStatefulWidget {
  /// Creates a thread screen.
  const ThreadScreen({
    required this.roomId,
    required this.threadId,
    super.key,
  });

  /// The ID of the room this thread belongs to.
  final String roomId;

  /// The ID of the thread to display, or 'new' for new thread intent.
  final String threadId;

  @override
  ConsumerState<ThreadScreen> createState() => _ThreadScreenState();
}

class _ThreadScreenState extends ConsumerState<ThreadScreen> {
  @override
  void initState() {
    super.initState();
    // Update providers on mount
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(currentRoomIdProvider.notifier).set(widget.roomId);

      // Handle 'new' threadId specially
      if (widget.threadId == 'new') {
        ref.read(threadSelectionProvider.notifier).set(const NewThreadIntent());
      } else {
        ref
            .read(threadSelectionProvider.notifier)
            .set(ThreadSelected(widget.threadId));
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final screenWidth = MediaQuery.of(context).size.width;
    final isDesktop = screenWidth >= 600;

    return Scaffold(
      appBar: AppBar(
        title: Text(_getTitle()),
        actions: [
          Builder(
            builder: (context) => IconButton(
              icon: const Icon(Icons.bug_report),
              tooltip: 'HTTP Inspector',
              onPressed: () => Scaffold.of(context).openEndDrawer(),
            ),
          ),
        ],
      ),
      endDrawer: const HttpInspectorPanel(),
      body: isDesktop ? _buildDesktopLayout() : _buildMobileLayout(),
    );
  }

  /// Builds the desktop layout with side-by-side panels.
  Widget _buildDesktopLayout() {
    return Row(
      children: [
        SizedBox(
          width: 300,
          child: Container(
            decoration: BoxDecoration(
              border: Border(
                right: BorderSide(
                  color: Theme.of(context).colorScheme.outlineVariant,
                ),
              ),
            ),
            child: const HistoryPanel(),
          ),
        ),
        const Expanded(
          child: ChatPanel(),
        ),
      ],
    );
  }

  /// Builds the mobile layout with chat only.
  Widget _buildMobileLayout() {
    return const ChatPanel();
  }

  /// Gets the title for the app bar.
  String _getTitle() {
    final room = ref.watch(currentRoomProvider);
    final thread = ref.watch(currentThreadProvider);

    if (room != null && thread != null && thread.hasName) {
      return thread.name;
    } else if (room != null) {
      return room.name;
    } else {
      return 'Chat';
    }
  }
}
