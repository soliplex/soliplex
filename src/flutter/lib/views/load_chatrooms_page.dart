import 'package:flutter/material.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:go_router/go_router.dart';

import 'package:soliplex_client/controllers.dart';
import 'package:soliplex_client/controllers/current_chatroom_controller.dart';
import 'package:soliplex_client/entities/chatroom_with_conversations.dart';
import 'package:soliplex_client/views/select_chatroom_view.dart';

class LoadChatroomsPage extends ConsumerStatefulWidget {
  const LoadChatroomsPage({super.key});

  @override
  ConsumerState<LoadChatroomsPage> createState() => _LoadChatroomsPageState();
}

class _LoadChatroomsPageState extends ConsumerState<LoadChatroomsPage> {
  late Future<Map<String, ChatroomWithConversations>> _dataFuture;

  Future<Map<String, ChatroomWithConversations>> _fetchData(
    CurrentChatroomController chatroomController,
  ) async {
    return await chatroomController.listAvailableChatrooms();
  }

  Future<void> _refreshData(
    CurrentChatroomController chatroomController,
  ) async {
    _dataFuture = _fetchData(chatroomController);
  }

  @override
  void initState() {
    super.initState();
    final chatroomController = ref.read(
      currentChatroomControllerProvider.notifier,
    );
    _dataFuture = _fetchData(chatroomController);
  }

  @override
  Widget build(BuildContext context) {
    final chatroomController = ref.read(
      currentChatroomControllerProvider.notifier,
    );

    return FutureBuilder(
      future: _dataFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return Center(
            child: CircularProgressIndicator(),
          ); // Show loading indicator
        } else if (snapshot.hasError) {
          final errorText = 'Error: ${snapshot.error}';
          debugPrint(errorText);
          return Column(
            children: [
              Text(errorText),
              ElevatedButton(
                onPressed: () async {
                  final refresh =
                      await showDialog(
                        context: context,
                        builder: (context) => AlertDialog(
                          content: Text('Would you like to refresh chatrooms?'),

                          actions: [
                            ElevatedButton(
                              onPressed: () => context.pop(true),
                              child: Text('Yes'),
                            ),
                            ElevatedButton(
                              onPressed: () => context.pop(false),
                              child: Text('No'),
                            ),
                          ],
                        ),
                      ) ??
                      false;

                  if (refresh) {
                    if (context.mounted) {
                      setState(() {
                        _refreshData(chatroomController);
                      });
                    }
                  }
                },
                child: Text('Refresh'),
              ),
            ],
          ); // Show error
        } else if (snapshot.hasData) {
          // If the future is complete and successful
          final chatroomConfigs = snapshot.data!;
          final chatrooms = chatroomConfigs.entries.toList();

          return SelectChatroomView(chatrooms: chatrooms);
        } else {
          return Text('Could not fetch chatrooms');
        }
      },
    );
  }
}
