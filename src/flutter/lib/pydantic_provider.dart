import 'package:flutter/foundation.dart';

import 'package:flutter_ai_toolkit/flutter_ai_toolkit.dart';
import 'package:soliplex_client/controllers/app_state_controller.dart';

import 'package:soliplex_client/controllers/current_chatroom_controller.dart';
import 'oidc_client.dart';

class PydanticAIProvider extends LlmProvider with ChangeNotifier {
  final OidcClient _oidcClient;
  final CurrentChatroomController chatroomController;
  final AppStateController appState;
  final List<ChatMessage> _history = [];
  final String _destinationUrl;
  final List<String> chatVariables;

  PydanticAIProvider(
    this._destinationUrl, {
    required OidcClient oidcClient,
    required this.chatroomController,
    required this.appState,
    required this.chatVariables,
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

  /// Converts ChatMessage from flutter_ai_toolkit to Map.
  Map<String, dynamic> _toMap(ChatMessage message) {
    return {
      'role': message.origin == MessageOrigin.user ? 'user' : 'assistant',
      'prompt': message.text,
    };
  }

  /// Converts the current chat history to a list of OpenAI messages.
  List<Map<String, dynamic>> _getAIChatHistory() {
    return _history.map((_toMap)).toList();
  }

  @override
  Stream<String> generateStream(
    String prompt, {
    Iterable<Attachment> attachments = const [],
  }) async* {
    // 0. Check if legal variable is used and replace
    String finalPrompt = prompt;
    for (var variable in chatVariables) {
      final stringVar = '\$$variable';
      if (prompt.contains(stringVar)) {
        try {
          final value = await appState.getVariable(variable);
          finalPrompt = prompt.replaceAll(stringVar, value);
        } catch (e) {
          debugPrint('Could not replace `$variable`. $e');
          finalPrompt = prompt;
        }
      }
    }

    // 1. Add the user message to history
    final userMessage = ChatMessage(
      text: finalPrompt,
      origin: MessageOrigin.user,
      attachments: attachments.toList(),
    );
    _history.add(userMessage);

    // 2. Prepare the messages for the OpenAI API call, including the new user prompt
    final messages = _getAIChatHistory();

    // 3. Create a new ChatMessage for the AI's response and add to history
    // This is how the LlmChatView tracks the AI's ongoing message.
    final llmResponse = ChatMessage(
      text: '', // Start with an empty text
      origin: MessageOrigin.llm,
      attachments: attachments.toList(),
    );

    _history.add(llmResponse);

    notifyListeners(); // Notify UI that history has changed (user message and empty LLM response added)

    try {
      if (_history.length <= 2) {
        final chatPageConfig = chatroomController.currentChatPageConfig;

        final chatRoomConfig = chatPageConfig.roomConfig;
        final (convoUuid, messageHistory) = await chatroomController
            .startNewConversation(chatRoomConfig.roomId, finalPrompt);

        chatroomController.updateConversationUuid(convoUuid);

        final lastllmMessage = messageHistory
            .where((e) => e.origin == MessageOrigin.llm)
            .last;

        if (lastllmMessage.text == null || lastllmMessage.text!.isEmpty) {
          throw Exception('Llm response is empty.');
        }

        _history[_history.length - 1] = messageHistory.last;

        notifyListeners(); // Notify UI that history has changed (user message and empty LLM response added)
      } else {
        final convoUuid = chatroomController.currentConversationUui();
        final convoDestination =
            '$_destinationUrl${convoUuid != null ? '/$convoUuid' : ''}';

        final chatStream = _oidcClient.postStream(
          to: convoDestination,
          prompt: messages.last['prompt'] ?? '',
          onSuccess: (output) => output,
          // You can add other parameters like temperature, maxTokens, etc.
          // temperature: 0.7,
          // maxTokens: 500,
        );

        final responseBuffer = <String>[''];
        await for (final chatCompletion in chatStream) {
          debugPrint('chatCompletion: $chatCompletion');
          if (chatCompletion['role'] == 'model') {
            responseBuffer.add(chatCompletion['content'] ?? '');
          }
          final updatedLlmResponse = ChatMessage(
            text: responseBuffer.last,
            origin: MessageOrigin.llm,
            attachments: attachments.toList(),
          );
          _history[_history.length - 1] =
              updatedLlmResponse; // Replace the last message
          notifyListeners(); // Notify UI for each chunk
          yield responseBuffer.last; // Yield the chunk to the LlmChatView
        }

        if (responseBuffer.last.isEmpty) {
          throw Exception('Llm response is empty.');
        }

        // Once the stream finishes, mark the message as not ongoing
        final finalLlmResponse = ChatMessage(
          text: responseBuffer.last,
          origin: MessageOrigin.llm,
          attachments: attachments.toList(),
        );
        _history[_history.length - 1] =
            finalLlmResponse; // Replace with final, non-ongoing message
        notifyListeners();
      }
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
