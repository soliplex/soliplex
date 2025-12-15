import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/network/connection_manager.dart';
import 'package:soliplex/core/network/server_room_key.dart';
import 'package:soliplex/core/providers/panel_providers.dart';
import 'package:soliplex/features/canvas/canvas_view.dart';
import 'package:soliplex/features/chat/chat_content.dart';

/// Canvas layout - 2/3 canvas + 1/3 chat.
///
/// Agent can push widgets to the canvas via tool calls.
/// The canvas displays rendered widgets in a scrollable list.
class CanvasLayout extends ConsumerWidget {
  const CanvasLayout({super.key, this.roomId});
  final String? roomId;

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
                        if (roomId != null) {
                          final serverId = ref
                              .read(connectionManagerProvider)
                              .activeServerId;
                          if (serverId != null) {
                            final key = ServerRoomKey(
                              serverId: serverId,
                              roomId: roomId!,
                            );
                            ref.read(roomCanvasProvider(key).notifier).clear();
                          }
                        }
                      },
                    ),
                  ],
                ),
              ),
              // Canvas content
              Expanded(child: CanvasView(roomId: roomId)),
            ],
          ),
        ),
        // Divider
        const VerticalDivider(width: 1),
        // Chat area (1/3 width) - ClipRect prevents overflow during scroll
        Expanded(
          child: ClipRect(child: ChatContent(roomId: roomId)),
        ),
      ],
    );
  }

  Widget _buildItemCount(BuildContext context, WidgetRef ref) {
    if (roomId == null) return const SizedBox.shrink();

    final serverId = ref.watch(connectionManagerProvider).activeServerId;
    if (serverId == null) return const SizedBox.shrink();

    final key = ServerRoomKey(serverId: serverId, roomId: roomId!);
    final canvasState = ref.watch(roomCanvasProvider(key));
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
