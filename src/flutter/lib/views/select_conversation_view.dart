import 'package:flutter/material.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:soliplex_client/controllers.dart';
import 'package:soliplex_client/controllers/current_chatroom_controller.dart';
import 'package:soliplex_client/entities/chatroom_config.dart';
import 'package:soliplex_client/entities/conversation_entry.dart';
import 'package:soliplex_client/entities/quiz_config.dart';

class SelectConversationView extends ConsumerWidget {
  const SelectConversationView({
    required this.config,
    required this.conversations,
    required this.quizzes,
    super.key,
  });

  final ChatroomConfig config;
  final List<ConversationEntry> conversations;
  final Map<String, QuizConfig> quizzes;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final chatroomController = ref.read(
      currentChatroomControllerProvider.notifier,
    );

    final buttonStyle = ButtonStyle(
      padding: WidgetStatePropertyAll(
        EdgeInsets.symmetric(horizontal: 12.0, vertical: 8.0),
      ),
      elevation: WidgetStatePropertyAll(0),
      shape: WidgetStatePropertyAll(
        RoundedRectangleBorder(
          borderRadius: BorderRadiusGeometry.circular(8.0),
        ),
      ),
      side: WidgetStatePropertyAll(
        BorderSide(color: Colors.grey.withAlpha(90)),
      ),
    );

    return SingleChildScrollView(
      child: Column(
        children: [
          buildConversationButtons(chatroomController, buttonStyle),
          quizzes.isEmpty
              ? Container()
              : buildQuizButtons(chatroomController, buttonStyle),
        ],
      ),
    );
  }

  Widget buildConversationButtons(
    CurrentChatroomController chatroomController,
    ButtonStyle buttonStyle,
  ) {
    return Column(
      children: [
        Align(alignment: Alignment.centerLeft, child: Text('Conversations')),
        ...conversations.map(
          (e) => Row(
            children: [
              Expanded(
                child: ExistingConversationButton(
                  style: buttonStyle,
                  chatroomController: chatroomController,
                  roomConfig: config,
                  convoConfig: e,
                ),
              ),
            ],
          ),
        ),
        NewConversationButton(
          style: buttonStyle,
          config: config,
          chatroomController: chatroomController,
        ),
      ],
    );
  }

  Widget buildQuizButtons(
    CurrentChatroomController chatroomController,
    ButtonStyle style,
  ) {
    return Column(
      children: [
        Align(alignment: Alignment.centerLeft, child: Text('Quizzes')),
        ...quizzes.values.map(
          (e) => Row(
            children: [
              Expanded(
                child: QuizButton(
                  chatroomController: chatroomController,
                  roomConfig: config,
                  quizConfig: e,
                  style: style,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class QuizButton extends StatelessWidget {
  const QuizButton({
    this.style,
    required this.chatroomController,
    required this.roomConfig,
    required this.quizConfig,
    super.key,
  });

  final ButtonStyle? style;
  final CurrentChatroomController chatroomController;
  final ChatroomConfig roomConfig;
  final QuizConfig quizConfig;

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: () async {
        final bgImage = await chatroomController.retrieveChatroomBgImage(
          roomConfig.roomId,
        );

        chatroomController.setCurrentChatPageConfig(
          roomId: roomConfig.roomId,
          welcomeMessage: roomConfig.welcomeMessage,
          suggestions: roomConfig.suggestions,
          enableAttachments: roomConfig.enableAttachments,
          imageBytes: bgImage,
        );

        if (context.mounted) {
          context.pop();
          context.go('/quiz/${quizConfig.id}');
        }
      },
      style: style,
      child: Text(quizConfig.title),
    );
  }
}

class ExistingConversationButton extends StatelessWidget {
  const ExistingConversationButton({
    this.style,
    required this.chatroomController,
    required this.roomConfig,
    required this.convoConfig,
    super.key,
  });

  final ButtonStyle? style;
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
            context.pop();
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
      style: style,
      child: Text(convoConfig.name, softWrap: true),
    );
  }
}

class NewConversationButton extends StatelessWidget {
  const NewConversationButton({
    this.style,
    required this.config,
    required this.chatroomController,
    super.key,
  });

  final ButtonStyle? style;
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
          context.pop();
          context.go('/chat/${config.roomId}');
        }
      },
      style: style,
      child: Text('New Conversation'),
    );
  }
}
