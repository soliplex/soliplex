import 'package:flutter/material.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:soliplex_client/controllers.dart';
import 'package:soliplex_client/entities/chatroom_with_conversations.dart';
import 'package:soliplex_client/views/select_conversation_view.dart';

class SelectChatroomView extends ConsumerWidget {
  const SelectChatroomView({required this.chatrooms, super.key});

  final List<MapEntry<String, ChatroomWithConversations>> chatrooms;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Container(
      alignment: Alignment.topCenter,
      padding: EdgeInsets.symmetric(vertical: 8.0, horizontal: 4.0),
      child: SingleChildScrollView(
        child: buildChatroomRows(chatrooms.map((e) => e.value).toList()),
      ),
    );
  }

  Widget buildChatroomRows(List<ChatroomWithConversations> chatrooms) {
    final chatroomButtons = <Widget>[];

    int startingIndex = chatrooms.length - 1;

    if (chatrooms.length.isOdd) {
      chatroomButtons.add(
        ChatroomRow(
          child1: ChatroomButton(chatroom: chatrooms[startingIndex]),
          child2: Container(),
        ),
      );
      startingIndex--;
    }

    for (int i = startingIndex; i > 0; i -= 2) {
      chatroomButtons.insert(
        0,
        ChatroomRow(
          child1: ChatroomButton(chatroom: chatrooms[i - 1]),
          child2: ChatroomButton(chatroom: chatrooms[i]),
        ),
      );
    }
    return Column(
      mainAxisAlignment: MainAxisAlignment.start,
      spacing: 8.0,
      children: chatroomButtons,
    );
  }
}

class ChatroomRow extends StatelessWidget {
  const ChatroomRow({required this.child1, required this.child2, super.key});

  final Widget child1;
  final Widget child2;

  @override
  Widget build(BuildContext context) {
    return Row(
      spacing: 8.0,
      children: [
        Expanded(child: child1),
        Expanded(child: child2),
      ],
    );
  }
}

class ChatroomButton extends ConsumerWidget {
  const ChatroomButton({required this.chatroom, super.key});

  final ChatroomWithConversations chatroom;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final chatroomController = ref.read(
      currentChatroomControllerProvider.notifier,
    );

    return ElevatedButton(
      onPressed: () async {
        final bgImage = await chatroomController.retrieveChatroomBgImage(
          chatroom.config.roomId,
        );

        if (context.mounted &&
            chatroom.conversations.isEmpty &&
            chatroom.quizzes.isEmpty) {
          chatroomController.setCurrentChatPageConfig(
            roomId: chatroom.config.roomId,
            welcomeMessage: chatroom.config.welcomeMessage,
            suggestions: chatroom.config.suggestions,
            enableAttachments: chatroom.config.enableAttachments,
            initialHistory: [],
            imageBytes: bgImage,
          );
          context.go('/chat/${chatroom.config.roomId}');
        } else {
          if (context.mounted) {
            await showDialog(
              context: context,
              builder: (context) => AlertDialog(
                title: Text('History'),
                content: SelectConversationView(
                  config: chatroom.config,
                  conversations: chatroom.conversations,
                  quizzes: chatroom.quizzes,
                ),
              ),
            );
          }
        }
      },
      child: Row(
        spacing: 8.0,
        children: [
          CircularLetterWidget(
            name: chatroom.config.roomId,
            width: 32.0,
            height: 32.0,
            onTap: null,
          ),
          Text(
            chatroom.config.roomId,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

class CircularLetterWidget extends StatelessWidget {
  const CircularLetterWidget({
    required this.name,
    required this.width,
    required this.height,
    required this.onTap,

    super.key,
  });

  final String name;
  final double width;
  final double height;
  final Function(String roomId)? onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap == null
          ? null
          : () {
              onTap!(name);
            },
      child: Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: Colors.blue[800],
          shape: BoxShape.circle,
        ),
        child: Center(
          child: Text(
            extractLettersFromName(),
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }

  String extractLettersFromName() {
    final words = name.toUpperCase().split(RegExp(r'[\s-]'));
    if (words.length > 1) {
      return '${words[0][0]}${words[1][0]}';
    } else if (words[0].length > 5) {
      return '${words.first[0]}${words.first[(words.first.length / 2).floor()]}';
    } else {
      return words.first[0];
    }
  }
}
