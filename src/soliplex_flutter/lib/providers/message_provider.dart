import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../client/client.dart';
import 'client_provider.dart';
import 'room_provider.dart';

/// Provider for the message stream for the current room.
///
/// This streams messages from the RoomSession which is the source of truth.
final messagesProvider = StreamProvider<List<ChatMessage>>((ref) {
  final client = ref.watch(soliplexClientProvider);
  final roomId = ref.watch(currentRoomProvider);

  if (roomId == null) {
    return const Stream.empty();
  }

  return client.getMessageStream(roomId);
});

/// Provider for messages in a specific room.
final roomMessagesProvider = StreamProvider.family<List<ChatMessage>, String>((
  ref,
  roomId,
) {
  final client = ref.watch(soliplexClientProvider);
  return client.getMessageStream(roomId);
});

/// Provider for getting current messages synchronously.
final currentMessagesProvider = Provider<List<ChatMessage>>((ref) {
  final client = ref.watch(soliplexClientProvider);
  final roomId = ref.watch(currentRoomProvider);

  if (roomId == null) {
    return [];
  }

  return client.getMessages(roomId);
});
