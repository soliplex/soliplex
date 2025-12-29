import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/network/connection_manager.dart';
import 'package:soliplex/core/network/server_room_key.dart';
import 'package:soliplex/core/providers/panel_providers.dart';
import 'package:soliplex/core/services/canvas_service.dart';
import 'package:soliplex/core/services/widget_registry.dart';

/// Canvas view widget that displays agent-pushed widgets.
///
/// Renders widgets from the canvas state using the widget registry.
class CanvasView extends ConsumerWidget {
  const CanvasView({super.key, this.roomId});
  final String? roomId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final registry = ref.watch(widgetRegistryProvider);

    if (roomId == null) {
      return _buildEmptyCanvas(context);
    }

    final connectionManager = ref.watch(connectionManagerProvider);
    final serverId = connectionManager.activeServerId;

    if (serverId == null) {
      return _buildEmptyCanvas(context);
    }

    final key = ServerRoomKey(serverId: serverId, roomId: roomId!);
    final canvasState = ref.watch(roomCanvasProvider(key));

    if (canvasState.isEmpty) {
      return _buildEmptyCanvas(context);
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: canvasState.items.length,
      itemBuilder: (context, index) {
        final item = canvasState.items[index];
        final widget = registry.build(
          context,
          item.widgetName,
          item.data,
          onEvent: (name, args) {
            debugPrint('Canvas widget event: $name, args: $args');
          },
        );

        return Padding(
          padding: const EdgeInsets.only(bottom: 16),
          child: _CanvasItemCard(
            item: item,
            child: widget ?? _buildUnknownWidget(context, item.widgetName),
            onRemove: () {
              ref.read(roomCanvasProvider(key).notifier).removeItem(item.id);
            },
          ),
        );
      },
    );
  }

  Widget _buildEmptyCanvas(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.dashboard_outlined,
            size: 64,
            color: Theme.of(context).colorScheme.outline,
          ),
          const SizedBox(height: 16),
          Text(
            'Canvas is empty',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              color: Theme.of(context).colorScheme.outline,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Ask the agent to display widgets here',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.outline,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildUnknownWidget(BuildContext context, String widgetName) {
    return Card(
      color: Colors.orange.shade50,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(Icons.help_outline, color: Colors.orange.shade700),
            const SizedBox(width: 12),
            Text('Unknown widget: $widgetName'),
          ],
        ),
      ),
    );
  }
}

/// Card wrapper for canvas items with remove button.
class _CanvasItemCard extends StatelessWidget {
  const _CanvasItemCard({
    required this.item,
    required this.child,
    required this.onRemove,
  });
  final CanvasItem item;
  final Widget child;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 2,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header with widget name and remove button
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              borderRadius: const BorderRadius.vertical(
                top: Radius.circular(12),
              ),
            ),
            child: Row(
              children: [
                Icon(
                  Icons.widgets_outlined,
                  size: 16,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Text(
                  item.widgetName,
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: Theme.of(context).colorScheme.primary,
                  ),
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.close, size: 16),
                  onPressed: onRemove,
                  visualDensity: VisualDensity.compact,
                  tooltip: 'Remove from canvas',
                ),
              ],
            ),
          ),
          // Widget content
          Padding(padding: const EdgeInsets.all(12), child: child),
        ],
      ),
    );
  }
}
