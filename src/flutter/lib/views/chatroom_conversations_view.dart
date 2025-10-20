import 'package:flutter/material.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:soliplex_client/controllers.dart';
import 'package:soliplex_client/controllers/current_chatroom_controller.dart';
import 'package:soliplex_client/entities/chatroom_config.dart';
import 'package:soliplex_client/entities/chatroom_with_conversations.dart';
import 'package:soliplex_client/entities/conversation_entry.dart';
import 'package:soliplex_client/entities/quiz_config.dart';
import 'package:soliplex_client/shared_widgets/background_image_stack.dart';

class ChatroomConversationView extends ConsumerStatefulWidget {
  const ChatroomConversationView({
    required this.chatroom,
    required this.onDelete,
    super.key,
  });

  final ChatroomWithConversations? chatroom;
  final Function(String roomId, String convoUuid) onDelete;

  @override
  ConsumerState<ChatroomConversationView> createState() =>
      _ChatroomConversationViewState();
}

class _ChatroomConversationViewState
    extends ConsumerState<ChatroomConversationView> {
  late List<ConversationEntry> _conversations;

  late Map<String, QuizConfig> _quizzes;

  @override
  void initState() {
    super.initState();
    _conversations = widget.chatroom?.conversations ?? [];
    _quizzes = widget.chatroom?.quizzes ?? {};
  }

  @override
  void didUpdateWidget(covariant ChatroomConversationView oldWidget) {
    super.didUpdateWidget(oldWidget);
    _conversations = widget.chatroom?.conversations ?? [];
    _quizzes = widget.chatroom?.quizzes ?? {};
  }

  @override
  Widget build(BuildContext context) {
    final chatroomController = ref.read(
      currentChatroomControllerProvider.notifier,
    );

    return BackgroundImageStack(
      image: AssetImage('assets/images/ic_launcher.png'),
      child: LayoutBuilder(
        builder: (context, constraints) => Container(
          width: constraints.maxWidth > 500 ? 500 : constraints.maxWidth - 32,
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(15.0)),
          child: SizedBox.expand(
            child: SingleChildScrollView(
              child: Column(
                children: [
                  buildConversationDisplay(context, chatroomController),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget buildConversationDisplay(
    BuildContext context,
    CurrentChatroomController chatroomController,
  ) {
    if (widget.chatroom == null) {
      return Container(color: Colors.transparent);
    }

    return Column(
      children: [
        Text(
          widget.chatroom!.config.roomId.toUpperCase(),
          style: TextStyle(fontSize: 18.0, fontWeight: FontWeight.bold),
        ),
        ..._conversations.map(
          (convo) => Padding(
            padding: const EdgeInsets.all(4.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: ExistingConversationButton(
                    chatroomController: chatroomController,
                    roomConfig: widget.chatroom!.config,
                    convoConfig: convo,
                  ),
                ),
                // Delete Conversation
                IconButton(
                  onPressed: () async {
                    final deleteConversation = await showDialog<bool>(
                      context: context,
                      builder: (context) => AlertDialog(
                        content: Text(
                          'Do you want to delete this conversation?',
                        ),
                        actions: [
                          ElevatedButton(
                            onPressed: () async {
                              context.pop(true);
                            },
                            child: Text('Yes'),
                          ),
                          ElevatedButton(
                            onPressed: () => context.pop(false),
                            child: Text('No'),
                          ),
                        ],
                      ),
                    );

                    if (deleteConversation ?? false) {
                      try {
                        await chatroomController.deleteConversation(convo.uuid);
                        final roomId = widget.chatroom!.config.roomId;
                        setState(() {
                          widget.onDelete(roomId, convo.uuid);
                        });
                        // });
                      } catch (e) {
                        if (context.mounted) {
                          ScaffoldMessenger.of(
                            context,
                          ).showSnackBar(SnackBar(content: Text(e.toString())));
                        }
                      }
                    }
                  },
                  icon: Icon(Icons.delete, color: Colors.red),
                ),
              ],
            ),
          ),
        ),
        // New Conversation
        Padding(
          padding: const EdgeInsets.all(4.0),
          child: NewConversationButton(
            chatroomController: chatroomController,
            config: widget.chatroom!.config,
          ),
        ),
        AvailableQuizzesList(
          config: widget.chatroom!.config,
          quizzes: _quizzes,
        ),
      ],
    );
  }
}

class ExistingConversationButton extends StatelessWidget {
  const ExistingConversationButton({
    super.key,
    required this.chatroomController,
    required this.roomConfig,
    required this.convoConfig,
  });

  final CurrentChatroomController chatroomController;
  final ChatroomConfig roomConfig;
  final ConversationEntry convoConfig;

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: () async {
        try {
          final conversation = await chatroomController.retrieveConversation(
            convoConfig.uuid,
          );

          final bgImage = await chatroomController.retrieveChatroomBgImage(
            roomConfig.roomId,
          );

          chatroomController.setCurrentChatPageConfig(
            roomId: roomConfig.roomId,
            conversationUuid: convoConfig.uuid,
            welcomeMessage: roomConfig.welcomeMessage,
            suggestions: roomConfig.suggestions,
            enableAttachments: roomConfig.enableAttachments,
            imageBytes: bgImage,
          );

          if (context.mounted) {
            context.go('/chat/${roomConfig.roomId}', extra: conversation);
          }
        } catch (e) {
          debugPrint('Error: $e');
          if (context.mounted) {
            ScaffoldMessenger.of(
              context,
            ).showSnackBar(SnackBar(content: Text(e.toString())));
          }
        }
      },
      style: ButtonStyle(
        padding: WidgetStatePropertyAll(
          EdgeInsets.symmetric(horizontal: 12.0, vertical: 8.0),
        ),
        shape: WidgetStatePropertyAll(
          RoundedRectangleBorder(
            borderRadius: BorderRadiusGeometry.circular(8.0),
          ),
        ),
      ),
      child: Text(
        convoConfig.name,
        softWrap: true,
        style: TextStyle(fontWeight: FontWeight.bold),
      ),
    );
  }
}

class NewConversationButton extends StatelessWidget {
  const NewConversationButton({
    super.key,
    required this.config,
    required this.chatroomController,
  });

  final CurrentChatroomController chatroomController;
  final ChatroomConfig config;

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: () async {
        final bgImage = await chatroomController.retrieveChatroomBgImage(
          config.roomId,
        );

        chatroomController.setCurrentChatPageConfig(
          roomId: config.roomId,
          welcomeMessage: config.welcomeMessage,
          suggestions: config.suggestions,
          enableAttachments: config.enableAttachments,
          imageBytes: bgImage,
        );

        if (context.mounted) {
          context.go('/chat/${config.roomId}');
        }
      },
      style: ButtonStyle(
        shape: WidgetStatePropertyAll<OutlinedBorder>(RoundedRectangleBorder()),
      ),
      child: Text(
        'New Conversation',
        style: TextStyle(fontWeight: FontWeight.bold),
      ),
    );
  }
}

class AvailableQuizzesList extends ConsumerWidget {
  final Map<String, QuizConfig> quizzes;
  final ChatroomConfig config;

  const AvailableQuizzesList({
    required this.config,
    required this.quizzes,
    super.key,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (quizzes.isEmpty) {
      return Container();
    }
    return Column(
      children: [
        Text('Quizzes'),
        ...quizzes.values.map(
          (e) => ElevatedButton(
            onPressed: () async {
              final chatroomController = ref.read(
                currentChatroomControllerProvider.notifier,
              );

              final bgImage = await chatroomController.retrieveChatroomBgImage(
                config.roomId,
              );

              chatroomController.setCurrentChatPageConfig(
                roomId: config.roomId,
                welcomeMessage: config.welcomeMessage,
                suggestions: config.suggestions,
                enableAttachments: config.enableAttachments,
                imageBytes: bgImage,
              );

              if (context.mounted) {
                context.go('/quiz/${e.id}');
              }
            },
            child: Text(e.title, style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ),
      ],
    );
  }
}
