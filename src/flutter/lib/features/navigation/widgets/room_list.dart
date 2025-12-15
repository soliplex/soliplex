import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:soliplex/core/services/rooms_service.dart';

class RoomList extends ConsumerWidget {
  const RoomList({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final roomsState = ref.watch(roomsProvider);
    final selectedRoom = ref.watch(selectedRoomProvider);

    if (roomsState.isLoading) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(16),
          child: CircularProgressIndicator(),
        ),
      );
    }

    if (roomsState.error != null) {
      return Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Error loading rooms',
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: () => ref.read(roomsProvider.notifier).fetchRooms(),
            ),
          ],
        ),
      );
    }

    if (roomsState.rooms.isEmpty) {
      return const ListTile(title: Text('No rooms found'));
    }

    return ListView.builder(
      shrinkWrap: true,
      physics: const ClampingScrollPhysics(),
      itemCount: roomsState.rooms.length,
      itemBuilder: (context, index) {
        final room = roomsState.rooms[index];
        final isSelected = room.id == selectedRoom;

        return ListTile(
          leading: const Icon(Icons.chat_bubble_outline),
          title: Text(room.name),
          selected: isSelected,
          onTap: () {
            context.go('/chat/${room.id}');
          },
        );
      },
    );
  }
}
