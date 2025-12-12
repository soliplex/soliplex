import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers/panel_providers.dart';
import '../../core/services/canvas_service.dart';
import '../../core/services/widget_registry.dart';

/// Canvas view widget that displays agent-pushed widgets.
///
/// Renders widgets from the canvas state using the widget registry.
class CanvasView extends ConsumerWidget {
  const CanvasView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final canvasState = ref.watch(canvasProvider);
    final registry = ref.watch(widgetRegistryProvider);

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
              ref.read(canvasProvider.notifier).removeItem(item.id);
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
  final CanvasItem item;
  final Widget child;
  final VoidCallback onRemove;

  const _CanvasItemCard({
    required this.item,
    required this.child,
    required this.onRemove,
  });

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
