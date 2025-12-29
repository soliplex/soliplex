import 'dart:async';
import 'package:equatable/equatable.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/network/connection_manager.dart';
import 'package:soliplex/core/services/rooms_service.dart';
import 'package:soliplex/core/utils/debug_log.dart';

/// Parameters passed from the router to the chat screen.
class ChatRouteParams extends Equatable {
  // Add serverId/threadId later if needed for deep linking across servers

  const ChatRouteParams({this.roomId});
  final String? roomId;

  @override
  List<Object?> get props => [roomId];
}

/// Controller that synchronizes Route Params -> App State.
///
/// Ensures that when the URL changes (roomId), the ConnectionManager
/// and selectedRoomProvider are updated to match.
class ChatScreenController
    extends AutoDisposeFamilyAsyncNotifier<void, ChatRouteParams> {
  @override
  Future<void> build(ChatRouteParams params) async {
    final roomId = params.roomId;

    // 1. Sync Room ID
    if (roomId != null) {
      final currentSelected = ref.read(selectedRoomProvider);

      // Update provider if different (avoids loops if provider drove the URL)
      if (currentSelected != roomId) {
        DebugLog.ui(
          'ChatScreenController: Syncing route roomId $roomId -> provider',
        );
        unawaited(
          Future.microtask(() {
            ref.read(selectedRoomProvider.notifier).state = roomId;
          }),
        );
      }

      // 2. Ensure ConnectionManager is switched
      final connectionManager = ref.read(connectionManagerProvider);

      // We must defer the side effect to avoid "modifying provider during
      // build" error
      // Note: This means the UI might render before switchRoom completes, but
      // since we pass roomId explicitly,
      // components should handle it gracefully.
      if (connectionManager.activeRoomId != roomId) {
        unawaited(
          Future.microtask(() {
            connectionManager.switchRoom(roomId);
          }),
        );
      }
    }
  }
}

final AutoDisposeAsyncNotifierProviderFamily<
  ChatScreenController,
  void,
  ChatRouteParams
>
chatScreenControllerProvider = AsyncNotifierProvider.autoDispose
    .family<ChatScreenController, void, ChatRouteParams>(
      ChatScreenController.new,
    );
