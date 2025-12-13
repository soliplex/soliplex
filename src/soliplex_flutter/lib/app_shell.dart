import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'features/canvas/canvas_feature.dart';
import 'features/chat/chat_feature.dart';
import 'features/details/details_feature.dart';
import 'features/history/history_feature.dart';
import 'providers/providers.dart';

/// Main app shell with responsive layout.
///
/// Layout structure:
/// ```
/// ┌─────────┬───────────────────────┬─────────────┐
/// │         │                       │  Details    │
/// │ History │       Canvas          │─────────────│
/// │  (1/4)  │  (Current/Permanent)  │    Chat     │
/// │         │                       │             │
/// └─────────┴───────────────────────┴─────────────┘
/// ```
class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  bool _historyExpanded = true;
  bool _detailsExpanded = true;
  int _canvasTabIndex = 0;

  @override
  Widget build(BuildContext context) {
    final roomId = ref.watch(currentRoomProvider);
    final isActive = ref.watch(isAgentActiveProvider);

    return Scaffold(
      appBar: _buildAppBar(roomId, isActive),
      body: _buildBody(),
    );
  }

  PreferredSizeWidget _buildAppBar(String? roomId, bool isActive) {
    return AppBar(
      title: Row(
        children: [
          const Text('Soliplex'),
          const SizedBox(width: 16),
          Expanded(child: _RoomSelector(currentRoomId: roomId)),
        ],
      ),
      backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      actions: [
        if (isActive)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: Row(
              children: [
                SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                ),
                const SizedBox(width: 8),
                const Text(
                  'Active',
                  style: TextStyle(fontSize: 12),
                ),
              ],
            ),
          ),
        IconButton(
          icon: Icon(_historyExpanded ? Icons.view_sidebar : Icons.view_sidebar_outlined),
          tooltip: _historyExpanded ? 'Hide History' : 'Show History',
          onPressed: () => setState(() => _historyExpanded = !_historyExpanded),
        ),
        IconButton(
          icon: Icon(_detailsExpanded ? Icons.info : Icons.info_outline),
          tooltip: _detailsExpanded ? 'Hide Details' : 'Show Details',
          onPressed: () => setState(() => _detailsExpanded = !_detailsExpanded),
        ),
        IconButton(
          icon: const Icon(Icons.bug_report),
          tooltip: 'Test Page',
          onPressed: () => Navigator.pushNamed(context, '/test'),
        ),
      ],
    );
  }

  Widget _buildBody() {
    return Row(
      children: [
        // History panel (collapsible)
        if (_historyExpanded) ...[
          SizedBox(
            width: 280,
            child: Container(
              decoration: BoxDecoration(
                border: Border(
                  right: BorderSide(
                    color: Theme.of(context).dividerColor,
                  ),
                ),
              ),
              child: const HistoryWidget(),
            ),
          ),
        ],

        // Main content (Canvas)
        Expanded(
          flex: 3,
          child: Column(
            children: [
              // Canvas tabs
              Container(
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
                    _CanvasTab(
                      label: 'Current',
                      icon: Icons.dashboard,
                      isSelected: _canvasTabIndex == 0,
                      onTap: () => setState(() => _canvasTabIndex = 0),
                    ),
                    _CanvasTab(
                      label: 'Pinned',
                      icon: Icons.push_pin,
                      isSelected: _canvasTabIndex == 1,
                      onTap: () => setState(() => _canvasTabIndex = 1),
                    ),
                  ],
                ),
              ),
              // Canvas content
              Expanded(
                child: _canvasTabIndex == 0
                    ? const CurrentCanvasWidget()
                    : const PermanentCanvasWidget(),
              ),
            ],
          ),
        ),

        // Right panel (Details + Chat, collapsible)
        if (_detailsExpanded) ...[
          Container(
            width: 400,
            decoration: BoxDecoration(
              border: Border(
                left: BorderSide(
                  color: Theme.of(context).dividerColor,
                ),
              ),
            ),
            child: Column(
              children: [
                // Details section (expandable)
                SizedBox(
                  height: 300,
                  child: Container(
                    decoration: BoxDecoration(
                      border: Border(
                        bottom: BorderSide(
                          color: Theme.of(context).dividerColor,
                        ),
                      ),
                    ),
                    child: const DetailsWidget(),
                  ),
                ),
                // Chat section
                const Expanded(child: ChatWidget()),
              ],
            ),
          ),
        ] else ...[
          // Compact chat when details collapsed
          Container(
            width: 350,
            decoration: BoxDecoration(
              border: Border(
                left: BorderSide(
                  color: Theme.of(context).dividerColor,
                ),
              ),
            ),
            child: const ChatWidget(),
          ),
        ],
      ],
    );
  }
}

class _RoomSelector extends ConsumerWidget {
  const _RoomSelector({required this.currentRoomId});

  final String? currentRoomId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final roomsAsync = ref.watch(roomsProvider);

    return roomsAsync.when(
      data: (rooms) {
        if (rooms.isEmpty) {
          return Text(
            'No rooms available',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.outline,
            ),
          );
        }

        return DropdownButton<String>(
          value: currentRoomId,
          hint: const Text('Select Room'),
          isExpanded: true,
          underline: const SizedBox.shrink(),
          items: rooms.map((room) {
            return DropdownMenuItem(
              value: room.id,
              child: Row(
                children: [
                  const Icon(Icons.meeting_room, size: 16),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      room.name,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            );
          }).toList(),
          onChanged: (roomId) {
            if (roomId != null) {
              ref.read(currentRoomProvider.notifier).state = roomId;
              ref.read(currentThreadProvider.notifier).state = null;
            }
          },
        );
      },
      loading: () => const SizedBox(
        width: 20,
        height: 20,
        child: CircularProgressIndicator(strokeWidth: 2),
      ),
      error: (error, _) => Text(
        'Error loading rooms',
        style: TextStyle(color: Theme.of(context).colorScheme.error),
      ),
    );
  }
}

class _CanvasTab extends StatelessWidget {
  const _CanvasTab({
    required this.label,
    required this.icon,
    required this.isSelected,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              color: isSelected ? theme.colorScheme.primary : Colors.transparent,
              width: 2,
            ),
          ),
        ),
        child: Row(
          children: [
            Icon(
              icon,
              size: 16,
              color: isSelected ? theme.colorScheme.primary : theme.colorScheme.outline,
            ),
            const SizedBox(width: 8),
            Text(
              label,
              style: TextStyle(
                color: isSelected ? theme.colorScheme.primary : theme.colorScheme.outline,
                fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
