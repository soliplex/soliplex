import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/shared/widgets/empty_state.dart';
import 'package:soliplex_frontend/shared/widgets/error_display.dart';
import 'package:soliplex_frontend/shared/widgets/loading_indicator.dart';

/// Screen displaying list of available rooms.
class RoomsScreen extends ConsumerWidget {
  const RoomsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final roomsAsync = ref.watch(roomsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Rooms'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => context.push('/settings'),
            tooltip: 'Settings',
          ),
        ],
      ),
      body: roomsAsync.when(
        data: (rooms) {
          if (rooms.isEmpty) {
            return const EmptyState(
              message: 'No rooms available',
              icon: Icons.meeting_room_outlined,
            );
          }

          return ListView.builder(
            itemCount: rooms.length,
            itemBuilder: (context, index) {
              final room = rooms[index];
              return ListTile(
                leading: const Icon(Icons.meeting_room),
                title: Text(room.name),
                subtitle:
                    room.description != null ? Text(room.description!) : null,
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  ref.read(currentRoomIdProvider.notifier).set(room.id);
                  context.push('/rooms/${room.id}');
                },
              );
            },
          );
        },
        loading: () => const LoadingIndicator(message: 'Loading rooms...'),
        error: (error, stack) => ErrorDisplay(
          error: error,
          onRetry: () => ref.invalidate(roomsProvider),
        ),
      ),
    );
  }
}
