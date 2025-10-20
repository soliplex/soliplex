import 'package:flutter/material.dart' hide MetaData;

import 'package:flutter_ai_toolkit/flutter_ai_toolkit.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:soliplex_client/controllers.dart';
import 'package:soliplex_client/entities/quizzes.dart';

class QuizPage extends ConsumerStatefulWidget {
  const QuizPage({
    required this.quizId,
    this.welcomeMessage,
    this.style,
    super.key,
  });

  final String quizId;
  final String? welcomeMessage;
  final LlmChatViewStyle? style;

  @override
  ConsumerState<QuizPage> createState() => _QuizRoomState();
}

class _QuizRoomState extends ConsumerState<QuizPage> {
  Widget? llmQuizView;

  Widget buildQuizView(LlmProvider provider, QuizEntry quizEntry) =>
      LlmQuizView(
        provider: provider,
        welcomeMessage: widget.welcomeMessage,
        quiz: quizEntry.toJson(),
        enableVoiceNotes: false,
        returnToRooms: () {
          if (context.mounted) {
            context.go('/chat');
          }
        },
        startOver: () {
          if (context.mounted) {
            setState(() {
              llmQuizView = null;
            });
            setState(() {
              llmQuizView = buildQuizView(provider, quizEntry);
            });
          }
        },
        style: widget.style,
        onErrorCallback: (context, error) async {
          await showDialog(
            context: context,
            barrierDismissible: false,
            builder: (context) => Builder(
              builder: (context) {
                return AlertDialog(
                  content: SingleChildScrollView(child: Text(error.toString())),
                  actions: [
                    TextButton(
                      onPressed: () {
                        GoRouter.of(context).go('/');
                        Navigator.pop(context);
                      },
                      child: const Text('Back'),
                    ),
                    TextButton(
                      onPressed: () {
                        Navigator.pop(context);
                      },
                      child: const Text('OK'),
                    ),
                  ],
                );
              },
            ),
          );
        },
      );

  @override
  Widget build(BuildContext context) {
    final chatroomController = ref.read(
      currentChatroomControllerProvider.notifier,
    );

    return FutureBuilder(
      future: chatroomController.retrieveQuiz(
        chatroomController.currentChatPageConfig.roomConfig.roomId,
        widget.quizId,
      ),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return Center(
            child: CircularProgressIndicator(),
          ); // Show loading indicator
        } else if (snapshot.hasError) {
          return Text('Error: ${snapshot.error}'); // Show error
        } else if (snapshot.hasData) {
          final quizEntry = snapshot.data!;
          final provider = ref
              .read(pydanticProviderController)
              .buildQuizProvider(chatroomController: chatroomController);
          llmQuizView = buildQuizView(provider, quizEntry);
          return Column(
            children: [
              Padding(
                padding: const EdgeInsets.all(8.0),
                child: SizedBox(
                  height: 32,
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'Quiz: ${quizEntry.id}',
                        style: TextStyle(fontSize: 20.0),
                      ),
                    ],
                  ),
                ),
              ),
              Expanded(child: Center(child: llmQuizView)),
            ],
          );
        } else {
          return Text("Could not load quiz '${widget.quizId}'");
        }
      },
    );
  }
}
