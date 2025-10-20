import 'package:flutter/material.dart';

import 'package:flutter_ai_toolkit/flutter_ai_toolkit.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:soliplex_client/controllers/current_chatroom_controller.dart';
import 'package:soliplex_client/controllers.dart';
import 'package:soliplex_client/shared_widgets/background_image_stack.dart';
import 'package:soliplex_client/views/chat_page.dart';
import 'package:soliplex_client/views/quiz_page.dart';

class Chatroom extends ConsumerStatefulWidget {
  const Chatroom({required this.llmProvider, this.quizId, super.key});

  final LlmProvider llmProvider;
  final String? quizId;

  @override
  ConsumerState<Chatroom> createState() => _ChatroomState();
}

class _ChatroomState extends ConsumerState<Chatroom> {
  Widget? child;

  @override
  Widget build(BuildContext context) {
    child = buildChatroomChild();

    final chatroomController = ref.read(
      currentChatroomControllerProvider.notifier,
    );

    final imageBytes = chatroomController.currentChatPageConfig.bgImageData;

    final conversationUuid = ref.watch(currentChatroomControllerProvider);

    return GestureDetector(
      onHorizontalDragEnd: (details) async {
        // Check if the swipe was to the right
        if (details.velocity.pixelsPerSecond.dx > 0) {
          if (context.mounted) {
            context.go('/chat');
          }
        }
      },
      child: BackgroundImageStack(
        image: imageBytes != null
            ? MemoryImage(imageBytes)
            : AssetImage('assets/images/ic_launcher.png'),
        child: Column(
          children: [
            Container(
              alignment: Alignment.topRight,
              padding: EdgeInsets.only(right: 4.0),
              child: widget.quizId == null
                  ? NewConversationButton(
                      chatroomController: chatroomController,
                      enabled: conversationUuid != null,
                      prompt:
                          'Would you like to start a new conversation?\n'
                          'You can return to this conversation later.',
                      onPressed: conversationUuid != null
                          ? () async {
                              widget.llmProvider.history = [];
                              chatroomController.updateConversationUuid(null);
                            }
                          : null,
                    )
                  : NewConversationButton(
                      chatroomController: chatroomController,
                      prompt:
                          'Would you like to restart?\n'
                          'You will lose your current progress in the quiz.',
                      enabled: true,
                      onPressed: () async {
                        setState(() {
                          child = buildChatroomChild();
                        });
                      },
                    ),
            ),
            Expanded(child: child ?? Container()),
          ],
        ),
      ),
    );
  }

  Widget buildChatroomChild() {
    final llmStyle = LlmChatViewStyle.resolve(
      LlmChatViewStyle(
        backgroundColor: Colors.transparent,
        userMessageStyle: UserMessageStyle.resolve(
          UserMessageStyle(
            textStyle: TextStyle(
              color: Colors.white,
              fontSize: 14.0,
              fontWeight: FontWeight.w600,
            ),
            decoration: BoxDecoration(
              color: Colors.blue[800],
              borderRadius: BorderRadius.only(
                topLeft: Radius.circular(20),
                topRight: Radius.zero,
                bottomLeft: Radius.circular(20),
                bottomRight: Radius.circular(20),
              ),
            ),
          ),
        ),
        llmMessageStyle: LlmMessageStyle.resolve(
          LlmMessageStyle(
            decoration: BoxDecoration(
              color: Colors.white,
              border: Border.all(color: Colors.grey),
              boxShadow: kElevationToShadow[32],
              borderRadius: const BorderRadius.only(
                topLeft: Radius.zero,
                topRight: Radius.circular(20),
                bottomLeft: Radius.circular(20),
                bottomRight: Radius.circular(20),
              ),
            ),
          ),
        ),
      ),
    );

    return widget.quizId == null
        ? ChatPage(llmProvider: widget.llmProvider, style: llmStyle)
        : QuizPage(quizId: widget.quizId!, style: llmStyle);
  }
}

class NewConversationButton extends StatelessWidget {
  const NewConversationButton({
    super.key,
    required this.chatroomController,
    required this.prompt,
    required this.enabled,
    required this.onPressed,
  });

  final CurrentChatroomController chatroomController;
  final String prompt;
  final bool enabled;
  final Function()? onPressed;

  @override
  Widget build(BuildContext context) {
    return TextButton(
      onPressed: (enabled && (onPressed != null))
          ? () async {
              final restart = await confirmUserChoice(context, prompt);
              if (restart) {
                onPressed!();
              }
            }
          : null,
      style: TextButton.styleFrom(
        padding: EdgeInsets.symmetric(horizontal: 4.0, vertical: 2.0),
        backgroundColor: enabled ? Colors.blue[700] : Colors.grey,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8.0)),
      ),
      child: Text(
        'New',
        style: TextStyle(
          color: enabled ? Colors.white : Colors.black,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Future<bool> confirmUserChoice(BuildContext context, String prompt) async {
    final choice = await showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('Confirmation'),
          content: Text(prompt),
          actions: <Widget>[
            TextButton(
              onPressed: () {
                // Close the dialog and return false
                Navigator.of(context).pop(false);
              },
              child: const Text('No'),
            ),
            TextButton(
              onPressed: () {
                // Close the dialog and return true
                Navigator.of(context).pop(true);
              },
              child: const Text('Yes'),
            ),
          ],
        );
      },
    );
    return choice;
  }
}
