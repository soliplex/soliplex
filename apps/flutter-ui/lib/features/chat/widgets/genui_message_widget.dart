import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/core/services/widget_registry.dart';

/// GenUI message widget that renders widgets from the registry.
///
/// Routes to the appropriate native widget based on [GenUiContent.widgetName]
/// using the WidgetRegistry.
class GenUiMessageWidget extends ConsumerWidget {
  const GenUiMessageWidget({
    required this.content,
    super.key,
    this.onEvent,
    this.maxHeight = 400,
  });
  final GenUiContent content;
  final void Function(String eventName, Map<String, dynamic> arguments)?
  onEvent;
  final double maxHeight;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final registry = ref.watch(widgetRegistryProvider);

    final widget = registry.build(
      context,
      content.widgetName,
      content.data,
      onEvent: onEvent,
    );

    if (widget == null) {
      return _buildUnknownWidget(context, registry);
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        return Container(
          constraints: BoxConstraints(
            maxHeight: maxHeight,
            maxWidth: constraints.maxWidth,
          ),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: Theme.of(context).colorScheme.outlineVariant,
            ),
          ),
          clipBehavior: Clip.antiAlias,
          child: SingleChildScrollView(
            child: Padding(padding: const EdgeInsets.all(12), child: widget),
          ),
        );
      },
    );
  }

  Widget _buildUnknownWidget(BuildContext context, WidgetRegistry registry) {
    debugPrint(
      'GenUiMessageWidget: Unknown widget encountered: ${content.widgetName}',
    );
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.orange.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.orange.shade200),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Icon(Icons.help_outline, color: Colors.orange.shade700),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  'Unknown widget: ${content.widgetName}',
                  style: TextStyle(
                    color: Colors.orange.shade700,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            'Available widgets:',
            style: TextStyle(
              color: Colors.orange.shade900,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 4),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            children: registry.registeredWidgets.map((name) {
              return Chip(
                label: Text(name, style: const TextStyle(fontSize: 12)),
                backgroundColor: Colors.orange.shade100,
                padding: EdgeInsets.zero,
                visualDensity: VisualDensity.compact,
              );
            }).toList(),
          ),
          if (content.data.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              'Received data:',
              style: TextStyle(
                color: Colors.orange.shade900,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 4),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.orange.shade100,
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                content.data.toString(),
                style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
