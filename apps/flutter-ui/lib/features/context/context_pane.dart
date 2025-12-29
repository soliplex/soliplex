import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/network/connection_manager.dart';
import 'package:soliplex/core/network/server_room_key.dart';
import 'package:soliplex/core/providers/panel_providers.dart';
import 'package:soliplex/core/services/context_pane_service.dart';

/// Context pane widget for displaying AG-UI activity and state.
///
/// Shows a compact activity feed with:
/// - AG-UI events (messages, tool calls, renders)
/// - Current state snapshot
/// - Tool results
class ContextPane extends ConsumerWidget {
  const ContextPane({super.key, this.roomId});
  final String? roomId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (roomId == null) {
      return const Center(
        child: Text(
          'Select a room to view activity',
          style: TextStyle(color: Colors.grey),
        ),
      );
    }

    final connectionManager = ref.watch(connectionManagerProvider);
    final serverId = connectionManager.activeServerId;

    if (serverId == null) {
      return const Center(
        child: Text('Not connected', style: TextStyle(color: Colors.grey)),
      );
    }

    final key = ServerRoomKey(serverId: serverId, roomId: roomId!);
    final contextState = ref.watch(roomContextPaneProvider(key));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            border: Border(
              bottom: BorderSide(
                color: Theme.of(context).colorScheme.outlineVariant,
              ),
            ),
          ),
          child: Row(
            children: [
              Icon(
                Icons.timeline,
                size: 16,
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(width: 8),
              Text('Activity', style: Theme.of(context).textTheme.titleSmall),
              const Spacer(),
              Text(
                '${contextState.items.length}',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.outline,
                ),
              ),
              const SizedBox(width: 8),
              IconButton(
                icon: const Icon(Icons.clear_all, size: 18),
                tooltip: 'Clear activity',
                visualDensity: VisualDensity.compact,
                onPressed: () {
                  ref.read(roomContextPaneProvider(key).notifier).clear();
                },
              ),
            ],
          ),
        ),
        // Current state section (if any)
        if (contextState.currentState.isNotEmpty) ...[
          _buildStateSection(context, contextState.currentState),
          Divider(
            height: 1,
            color: Theme.of(context).colorScheme.outlineVariant,
          ),
        ],
        // Activity feed
        Expanded(
          child: contextState.items.isEmpty
              ? _buildEmptyState(context)
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  itemCount: contextState.items.length,
                  itemBuilder: (context, index) {
                    final item = contextState.items[index];
                    return _ActivityRow(item: item);
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.hourglass_empty,
            size: 32,
            color: Theme.of(context).colorScheme.outline.withAlpha(100),
          ),
          const SizedBox(height: 8),
          Text(
            'No activity yet',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.outline,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStateSection(
    BuildContext context,
    Map<String, dynamic> stateData,
  ) {
    return Container(
      padding: const EdgeInsets.all(8),
      color: Theme.of(context).colorScheme.primaryContainer.withAlpha(30),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.data_object,
                size: 12,
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(width: 4),
              Text(
                'State',
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: Theme.of(context).colorScheme.primary,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          ...stateData.entries.take(5).map((e) {
            final value = e.value.toString();
            final displayValue = value.length > 30
                ? '${value.substring(0, 30)}...'
                : value;
            return Padding(
              padding: const EdgeInsets.only(bottom: 2),
              child: Text(
                '${e.key}: $displayValue',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  fontSize: 10,
                  fontFamily: 'monospace',
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            );
          }),
          if (stateData.length > 5)
            Text(
              '+${stateData.length - 5} more',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                fontSize: 10,
                color: Theme.of(context).colorScheme.outline,
              ),
            ),
        ],
      ),
    );
  }
}

/// Compact row widget for displaying an activity item.
class _ActivityRow extends StatelessWidget {
  const _ActivityRow({required this.item});
  final ContextItem item;

  @override
  Widget build(BuildContext context) {
    final (icon, color) = _getIconAndColor(item.type, item.title);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).colorScheme.outlineVariant.withAlpha(50),
          ),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Time
          SizedBox(
            width: 44,
            child: Text(
              _formatTime(item.timestamp),
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                fontSize: 10,
                color: Theme.of(context).colorScheme.outline,
                fontFamily: 'monospace',
              ),
            ),
          ),
          // Icon
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 6),
          // Content
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.title,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    fontWeight: FontWeight.w500,
                    fontSize: 11,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                if (item.summary != null)
                  Text(
                    item.summary!,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      fontSize: 10,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                // Show compact data for tool results
                if (item.type == 'tool_result' && item.data.isNotEmpty)
                  Text(
                    _formatDataCompact(item.data),
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      fontSize: 10,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                      fontFamily: 'monospace',
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  (IconData, Color) _getIconAndColor(String type, String title) {
    switch (type) {
      case 'agui_event':
        if (title.contains('User')) {
          return (Icons.person_outline, Colors.blue.shade400);
        } else if (title.contains('Agent')) {
          return (Icons.smart_toy_outlined, Colors.purple.shade400);
        } else if (title.contains('Tool:')) {
          return (Icons.build_outlined, Colors.orange.shade400);
        } else if (title.contains('GenUI')) {
          return (Icons.widgets_outlined, Colors.teal.shade400);
        } else if (title.contains('Canvas')) {
          return (Icons.dashboard_outlined, Colors.indigo.shade400);
        } else if (title.contains('Run')) {
          return (Icons.play_arrow_outlined, Colors.green.shade400);
        } else if (title.contains('Error')) {
          return (Icons.error_outline, Colors.red.shade400);
        } else if (title.contains('Thinking')) {
          return (Icons.psychology_outlined, Colors.amber.shade400);
        }
        return (Icons.circle_outlined, Colors.grey.shade400);
      case 'tool_result':
        return (Icons.check_circle_outline, Colors.green.shade400);
      case 'state':
        return (Icons.data_object, Colors.blue.shade400);
      case 'event':
        return (Icons.event, Colors.grey.shade400);
      default:
        return (Icons.circle_outlined, Colors.grey.shade400);
    }
  }

  String _formatTime(DateTime time) {
    return '${time.hour.toString().padLeft(2, '0')}:'
        '${time.minute.toString().padLeft(2, '0')}:'
        '${time.second.toString().padLeft(2, '0')}';
  }

  String _formatDataCompact(Map<String, dynamic> data) {
    // Show just the key values compactly
    final parts = <String>[];
    for (final entry in data.entries.take(3)) {
      final value = entry.value.toString();
      final short = value.length > 15 ? '${value.substring(0, 15)}…' : value;
      parts.add('${entry.key}=$short');
    }
    if (data.length > 3) {
      parts.add('+${data.length - 3}');
    }
    return parts.join(' ');
  }
}
