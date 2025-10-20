import 'package:flutter_ai_toolkit/flutter_ai_toolkit.dart';

import 'package:soliplex_client/controllers/current_chatroom_controller.dart';
import 'package:soliplex_client/oidc_client.dart';
import 'package:soliplex_client/pydantic_provider.dart';
import 'package:soliplex_client/pydantic_quiz_provider.dart';

import 'app_state_controller.dart';

class PydanticProviderController {
  PydanticProviderController({
    required this.baseServiceUrl,
    required this.destinationUrl,
    required this.destinationQuizUrl,
    required this.oidcClient,
    required this.chatVariables,
  });

  PydanticProviderController.newDestinationUrlFromExistingController(
    String newUrl,
    PydanticProviderController current,
  ) : baseServiceUrl = newUrl,
      destinationUrl = '$newUrl/v1/convos',
      destinationQuizUrl = '$newUrl/v1/rooms',
      oidcClient = current.oidcClient,
      chatVariables = current.chatVariables;

  final String baseServiceUrl;
  final String destinationUrl;
  final String destinationQuizUrl;
  final OidcClient oidcClient;
  final List<String> chatVariables;

  LlmProvider buildProvider({
    required CurrentChatroomController chatroomController,
    required AppStateController appStateController,
    List<ChatMessage>? initialHistory,
  }) {
    final pydanticProvider = PydanticAIProvider(
      destinationUrl,
      oidcClient: oidcClient,
      initialHistory: initialHistory,
      chatroomController: chatroomController,
      appState: appStateController,
      chatVariables: chatVariables,
    );

    return pydanticProvider;
  }

  LlmProvider buildQuizProvider({
    required CurrentChatroomController chatroomController,
    List<ChatMessage>? initialHistory,
  }) {
    final pydanticProvider = PydanticAIQuizProvider(
      destinationQuizUrl,
      oidcClient: oidcClient,
      initialHistory: initialHistory,
      chatroomController: chatroomController,
    );

    return pydanticProvider;
  }
}
