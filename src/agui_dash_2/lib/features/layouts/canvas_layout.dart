import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers/panel_providers.dart';
import '../canvas/canvas_view.dart';
import '../chat/chat_content.dart';

/// Canvas layout - 2/3 canvas + 1/3 chat.
///
/// Agent can push widgets to the canvas via tool calls.
/// The canvas displays rendered widgets in a scrollable list.
class CanvasLayout extends ConsumerWidget {
  const CanvasLayout({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Row(
      children: [
        // Canvas area (2/3 width)
        Expanded(
          flex: 2,
          child: Column(
            children: [
              // Canvas toolbar
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surfaceContainerLow,
                  border: Border(
                    bottom: BorderSide(
                      color: Theme.of(context).colorScheme.outlineVariant,
                    ),
                  ),
                ),
                child: Row(
                  children: [
                    Text(
                      'Canvas',
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                    const SizedBox(width: 8),
                    _buildItemCount(context, ref),
                    const Spacer(),
                    IconButton(
                      icon: const Icon(Icons.clear_all),
                      tooltip: 'Clear canvas',
                      onPressed: () {
                        ref.read(canvasProvider.notifier).clear();
                      },
                    ),
                  ],
                ),
              ),
              // Canvas content
              const Expanded(child: CanvasView()),
            ],
          ),
        ),
        // Divider
        const VerticalDivider(width: 1),
        // Chat area (1/3 width) - ClipRect prevents overflow during scroll
        Expanded(
          flex: 1,
          child: ClipRect(child: const ChatContent()),
        ),
      ],
    );
  }

  Widget _buildItemCount(BuildContext context, WidgetRef ref) {
    final canvasState = ref.watch(canvasProvider);
    final count = canvasState.items.length;

    if (count == 0) return const SizedBox.shrink();

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        '$count item${count == 1 ? '' : 's'}',
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
          color: Theme.of(context).colorScheme.onPrimaryContainer,
        ),
      ),
    );
  }
}
