import 'dart:convert';

import 'package:flutter/foundation.dart';

import 'package:flutter_ai_toolkit/flutter_ai_toolkit.dart';

import 'package:soliplex_client/controllers/current_chatroom_controller.dart';
import 'oidc_client.dart';

class PydanticAIQuizProvider extends LlmProvider with ChangeNotifier {
  final OidcClient _oidcClient;
  final CurrentChatroomController chatroomController;
  final List<ChatMessage> _history = [];
  final String _destinationUrl;

  PydanticAIQuizProvider(
    this._destinationUrl, {
    required OidcClient oidcClient,
    required this.chatroomController,
    Iterable<ChatMessage>? initialHistory,
  }) : _oidcClient = oidcClient {
    if (initialHistory != null) {
      _history.addAll(initialHistory);
    }
  }

  @override
  Iterable<ChatMessage> get history => _history;

  @override
  set history(Iterable<ChatMessage> newHistory) {
    _history.clear();
    _history.addAll(newHistory);
    notifyListeners();
  }

  @override
  Stream<String> generateStream(
    String prompt, {
    Iterable<Attachment> attachments = const [],
  }) async* {
    final Map decodedPrompt = jsonDecode(prompt);
    final roomId = decodedPrompt['roomId'] ?? '';
    final quizId = decodedPrompt['quizId'] ?? '';
    final questionId = decodedPrompt['questionId'] ?? '';
    final message = decodedPrompt['message'];

    // 1. Add the user message to history
    final userMessage = ChatMessage(
      text: message,
      origin: MessageOrigin.user,
      attachments: attachments.toList(),
    );
    _history.add(userMessage);

    // 2. Create a new ChatMessage for the AI's response and add to history
    // This is how the LlmChatView tracks the AI's ongoing message.
    final llmResponse = ChatMessage(
      text: '', // Start with an empty text
      origin: MessageOrigin.llm,
      attachments: attachments.toList(),
    );

    _history.add(llmResponse);

    notifyListeners(); // Notify UI that history has changed (user message and empty LLM response added)
    try {
      // destination url expected to be: '$base/$version/quizzes'
      final quizDestination =
          '$_destinationUrl/$roomId/quiz/$quizId/$questionId';

      final chatStream = _oidcClient.postStream(
        to: quizDestination,
        prompt: message,
        onSuccess: (output) => output,
        // You can add other parameters like temperature, maxTokens, etc.
        // temperature: 0.7,
        // maxTokens: 500,
      );

      final responseBuffer = <String>[''];
      await for (final chatCompletion in chatStream) {
        debugPrint('chatCompletion: $chatCompletion');
        final correct = (chatCompletion['correct'] ?? 'false') == 'true';

        responseBuffer.add(correct ? 'Correct!' : 'Incorrect.');

        final updatedLlmResponse = ChatMessage(
          text: responseBuffer.last,
          origin: MessageOrigin.llm,
          attachments: attachments.toList(),
        );
        _history[_history.length - 1] =
            updatedLlmResponse; // Replace the last message
        notifyListeners(); // Notify UI for each chunk
        debugPrint('returning response buffer.last: ${responseBuffer.last}');
        yield responseBuffer.last; // Yield the chunk to the LlmChatView
      }
      // Once the stream finishes, mark the message as not ongoing
      final finalLlmResponse = ChatMessage(
        text: responseBuffer.last,
        origin: MessageOrigin.llm,
        attachments: attachments.toList(),
      );
      _history[_history.length - 1] =
          finalLlmResponse; // Replace with final, non-ongoing message
      debugPrint('final history content: ${_history[_history.length - 1]}');
      notifyListeners();
    } catch (e, stacktrace) {
      // Handle errors: Remove the "ongoing" message and add an error message
      _history.removeLast(); // Remove the incomplete ongoing message
      final errorMessage = ChatMessage(
        text: 'Error: ${e.toString()}',
        origin: MessageOrigin.llm, // Still from LLM, but an error
        attachments: attachments.toList(),
        // isError: true, // Mark as an error message
      );
      _history.add(errorMessage);
      notifyListeners();
      debugPrint('Error in OpenAI generateStream: $e\n$stacktrace');
      rethrow; // Re-throw to propagate the error if needed
    }
  }

  @override
  Stream<String> sendMessageStream(
    String prompt, {
    Iterable<Attachment> attachments = const [],
  }) {
    return generateStream(prompt, attachments: attachments);
  }
}
