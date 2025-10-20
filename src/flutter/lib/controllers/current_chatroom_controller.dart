import 'dart:convert';

import 'package:flutter/foundation.dart';

import 'package:flutter_ai_toolkit/flutter_ai_toolkit.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex_client/entities/chatpage_config.dart';
import 'package:soliplex_client/entities/chatroom_config.dart';
import 'package:soliplex_client/entities/chatroom_with_conversations.dart';
import 'package:soliplex_client/entities/conversation_entry.dart';
import 'package:soliplex_client/entities/quizzes.dart';
import 'package:soliplex_client/oidc_client.dart';

class CurrentChatroomController extends StateNotifier<String?> {
  ChatroomProvider _chatroomProvider;
  ChatpageConfig _chatpageConfig;
  final Duration _shortTimeoutDuration;
  final Duration _longTimeoutDuration;

  CurrentChatroomController(
    this._chatroomProvider, {
    required String defaultRoomId,
    required Duration shortTimeoutDuration,
    required Duration longTimeoutDuration,
  }) : _chatpageConfig = ChatpageConfig(
         roomConfig: ChatroomConfig(roomId: defaultRoomId),
         initialMessages: [],
         bgImageData: null,
       ),
       _shortTimeoutDuration = shortTimeoutDuration,
       _longTimeoutDuration = longTimeoutDuration,
       super(null);

  void setNewProvider(String newUrl, OidcClient client) {
    _chatroomProvider = RemoteChatroomProvider(
      baseEndpoint: newUrl,
      oidcClient: client,
    );
  }

  ChatpageConfig get currentChatPageConfig => _chatpageConfig;

  String? currentConversationUui() => state;

  void setCurrentChatPageConfig({
    required String roomId,
    String? conversationUuid,
    String? welcomeMessage,
    List<String>? suggestions,
    bool? enableAttachments,
    List<ChatMessage>? initialHistory,
    Uint8List? imageBytes,
  }) {
    final chatroomConfig = ChatroomConfig(
      roomId: roomId,
      welcomeMessage: welcomeMessage,
      suggestions: suggestions,
      enableAttachments: enableAttachments,
    );

    _chatpageConfig = ChatpageConfig(
      roomConfig: chatroomConfig,
      initialMessages: initialHistory ?? [],
      bgImageData: imageBytes,
    );

    state = conversationUuid;
  }

  void updateConversationUuid(String? convoUuid) {
    state = convoUuid;
  }

  Future<ChatroomConfig> requestChatroom(String id) async {
    final chatroomString = await _chatroomProvider.retrieveChatroom(id);
    final json = jsonDecode(chatroomString) as Map<String, dynamic>;
    final chatroomConfig = ChatroomConfig.fromJson(json);
    return chatroomConfig;
  }

  Future<Map<String, ChatroomWithConversations>>
  listAvailableChatrooms() async {
    final chatroomsJson = await _chatroomProvider.listAvailableChatrooms();
    final chatrooms = <String, ChatroomWithConversations>{};
    for (final json in chatroomsJson) {
      final roomMap = jsonDecode(json);
      final config = ChatroomConfig.fromJson(roomMap);
      final chatroom = ChatroomWithConversations(
        config: config,
        conversations: [],
        quizzes: config.quizzes ?? {},
      );
      chatrooms[config.roomId] = chatroom;
    }

    try {
      final conversations = await retrieveConversations();
      for (final conversation in conversations) {
        if (chatrooms[conversation.roomId] != null) {
          chatrooms[conversation.roomId]!.conversations.add(conversation);
        } else {
          debugPrint(
            'Attempted to add "${conversation.name} (${conversation.uuid})" to chatroom "${conversation.roomId}", but it does not exist.',
          );
        }
      }
    } catch (e) {
      debugPrint('Exception retrieving conversations. $e');
    }

    return chatrooms;
  }

  Future<List<ConversationEntry>> retrieveConversations() async {
    final conversationEntries = await _chatroomProvider.retrieveConversations();
    final conversations = <ConversationEntry>[];

    for (final entry in conversationEntries.entries) {
      if (entry.key == 'detail') {
        continue;
      } else {
        final uuid = entry.key;
        final name = entry.value['name'];
        final roomId = entry.value['room_id'];

        conversations.add(
          ConversationEntry(uuid: uuid, name: name, roomId: roomId),
        );
      }
    }
    return conversations;
  }

  Future<(String, List<ChatMessage>)> startNewConversation(
    String roomId,
    String initialMessage,
  ) async {
    final conversationResponse = await _chatroomProvider.startNewConversation(
      roomId,
      initialMessage,
      _longTimeoutDuration,
    );

    final uuid = conversationResponse['convo_uuid'] as String;
    final messageHistory = List<Map<String, dynamic>>.from(
      conversationResponse['message_history'],
    );

    final messages = decodeChatMessages(messageHistory);

    return (uuid, messages);
  }

  Future<List<ChatMessage>> retrieveConversation(String convoId) async {
    final conversations = await _chatroomProvider.retrieveConversation(convoId);

    final messageHistory = decodeChatMessages(conversations);

    return messageHistory;
  }

  List<ChatMessage> decodeChatMessages(
    List<Map<String, dynamic>> jsonMessages,
  ) {
    final messages = <ChatMessage>[];

    for (final message in jsonMessages) {
      final jsonOrigin = message['origin'] as String;
      final jsonText = message['text'] as String;

      messages.add(
        ChatMessage(
          origin: MessageOrigin.values.firstWhere(
            (origin) => origin.name == jsonOrigin,
          ),
          text: jsonText,
          attachments: [],
        ),
      );
    }
    return messages;
  }

  Future<void> deleteConversation(String convoId) async {
    await _chatroomProvider.deleteConversation(convoId);
    state = null;
  }

  Future<QuizEntry> retrieveQuiz(String roomId, String quizId) async {
    final quizEntryJson = await _chatroomProvider.getQuiz(roomId, quizId);
    quizEntryJson['room_id'] = roomId;
    final quizEntry = QuizEntry.fromJson(quizEntryJson);

    return quizEntry;
  }

  Future<Map<String, dynamic>> retrieveChatroomInformation({
    required String roomId,
  }) async {
    final chatroomInfo = await _chatroomProvider.getChatroomInformation(
      roomId: roomId,
      timeout: _shortTimeoutDuration,
    );

    try {
      final prompt = await _chatroomProvider.getChatroomPrompt(roomId: roomId);
      String formattedResponse = prompt
          // Remove trailing "
          .replaceFirst('"', '', prompt.length - 1)
          // Remove leading "
          .replaceFirst('"', '')
          // Replace newlines with actual newline chars
          .replaceAll(r'\n', '\n')
          // Replace escaped " with actual quote
          .replaceAll(r'\"', '"');
      chatroomInfo['prompt'] = formattedResponse;
    } catch (e) {
      debugPrint('Failed to get chatroom prompt for `$roomId`. $e');
    }

    if (chatroomInfo['allow_mcp'] ?? false) {
      try {
        final mcpTokenMap = await _chatroomProvider.getMcpToken(
          roomId,
          _shortTimeoutDuration,
        );
        final mcpToken = mcpTokenMap['mcp_token'] as String?;
        if (mcpToken != null) {
          chatroomInfo['mcp_token'] = mcpToken;
        }
      } catch (e) {
        debugPrint('Failed to get an mcp token for `$roomId`. $e');
      }
    }
    return chatroomInfo;
  }

  Future<Uint8List?> retrieveChatroomBgImage(String roomId) async {
    final imageBytes = await _chatroomProvider.getChatroomBgImage(
      roomId: roomId,
    );
    return imageBytes;
  }

  Future<List<String>> requestLoginSystems() async {
    final loginSystems = await _chatroomProvider.getLoginSystems(
      _shortTimeoutDuration,
    );

    final systems = List<String>.from(loginSystems.values.map((e) => e['id']));

    return systems;
  }

  Future<String?> retrieveMcpToken(String roomId) async {
    final mcpToken = await _chatroomProvider.getMcpToken(
      roomId,
      _shortTimeoutDuration,
    );

    return mcpToken['mcp_token'];
  }

  Future<Map<String, dynamic>> retrieveUserInfo() async {
    final userKeysToKeep = [
      'name',
      'preferred_username',
      'given_name',
      'family_name',
      'email',
      'email_verified',
      'scope',
    ];
    final userInfo = await _chatroomProvider.getUserInfo(_shortTimeoutDuration);

    Map<String, dynamic> extractedUserKeys = {
      for (final key in userKeysToKeep)
        if (userInfo.containsKey(key)) key: userInfo[key],
    };

    // Format scope field
    if (extractedUserKeys.containsKey('scope') &&
        extractedUserKeys['scope'] is String) {
      extractedUserKeys['scope'] = (extractedUserKeys['scope'] as String)
          .replaceAll(' ', ', ');
    }

    return extractedUserKeys;
  }
}

abstract class ChatroomProvider {
  Future<List<String>> listAvailableChatrooms();
  Future<String> retrieveChatroom(String id);
  Future<Map<String, dynamic>> retrieveConversations();
  Future<Map<String, dynamic>> startNewConversation(
    String roomId,
    String initialMessage,
    Duration timeout,
  );
  Future<List<Map<String, dynamic>>> retrieveConversation(String convoId);
  Future<void> deleteConversation(String convoId);
  Future<Map<String, dynamic>> getQuiz(String roomId, String quizId);
  Future<Map<String, dynamic>> getChatroomInformation({
    required String roomId,
    required Duration timeout,
  });
  Future<String> getChatroomPrompt({required String roomId});
  Future<Uint8List?> getChatroomBgImage({required String roomId});
  Future<Map<String, dynamic>> getLoginSystems(Duration timeout);
  Future<Map<String, dynamic>> getMcpToken(String roomId, Duration timeout);
  Future<Map<String, dynamic>> getUserInfo(Duration timeout);
}

class RemoteChatroomProvider implements ChatroomProvider {
  RemoteChatroomProvider({required baseEndpoint, required oidcClient})
    : _baseEndpoint = baseEndpoint,
      _oidcClient = oidcClient;

  final String _baseEndpoint;
  final OidcClient _oidcClient;

  @override
  Future<List<String>> listAvailableChatrooms() async {
    final chatroomListUrl = '$_baseEndpoint/v1/rooms';

    final chatroomsResponse = await _oidcClient.get(Uri.parse(chatroomListUrl));

    if (chatroomsResponse.statusCode != 200) {
      throw Exception(
        'Could not load chatrooms. Status code: ${chatroomsResponse.statusCode}',
      );
    }

    final chatroomJson =
        jsonDecode(chatroomsResponse.body) as Map<String, dynamic>;

    final chatRooms = <String>[];

    for (final roomString in chatroomJson.entries) {
      chatRooms.add(jsonEncode(roomString.value));
    }

    return chatRooms;
  }

  @override
  Future<String> retrieveChatroom(String id) async {
    final chatroomsJson = await listAvailableChatrooms();

    for (final roomJson in chatroomsJson) {
      final room = jsonDecode(roomJson) as Map<String, dynamic>;
      if (room['roomid'] == id) {
        return jsonEncode(room);
      }
    }
    throw Exception('No room with id $id');
  }

  @override
  Future<Map<String, dynamic>> retrieveConversations() async {
    final conversationsUrl = '$_baseEndpoint/v1/convos';
    final conversationsResponse = await _oidcClient.get(
      Uri.parse(conversationsUrl),
    );

    if (conversationsResponse.statusCode != 200) {
      throw Exception(
        'Could not load conversations. Status code: ${conversationsResponse.statusCode}',
      );
    }

    final conversationsJson =
        jsonDecode(conversationsResponse.body) as Map<String, dynamic>;

    return conversationsJson;
  }

  @override
  Future<Map<String, dynamic>> startNewConversation(
    String roomId,
    String initialMessage,
    Duration timeout,
  ) async {
    final newConversationUrl = '$_baseEndpoint/v1/convos/new/$roomId';
    final body = jsonEncode({'text': initialMessage});
    final newConversationResponse = await _oidcClient.postWithTimeout(
      Uri.parse(newConversationUrl),
      headers: {'content-type': 'application/json'},
      body: body,
      timeLimit: timeout,
    );

    if (newConversationResponse.statusCode != 200) {
      throw Exception(
        "Could not start a new conversation in room '$roomId'. Status code: ${newConversationResponse.statusCode}",
      );
    }

    return jsonDecode(newConversationResponse.body) as Map<String, dynamic>;
  }

  @override
  Future<List<Map<String, dynamic>>> retrieveConversation(
    String convoId,
  ) async {
    final retrieveConversationUrl = '$_baseEndpoint/v1/convos/$convoId';
    final retrieveConversationResponse = await _oidcClient.get(
      Uri.parse(retrieveConversationUrl),
    );

    if (retrieveConversationResponse.statusCode != 200) {
      throw Exception(
        "Could not load conversation with uuid '$convoId'. Status code: ${retrieveConversationResponse.statusCode}",
      );
    }

    final retrievedJson = retrieveConversationResponse.body;
    final decoded = jsonDecode(retrievedJson) as Map<String, dynamic>;

    return List<Map<String, dynamic>>.from(decoded['message_history']);
  }

  @override
  Future<void> deleteConversation(String convoId) async {
    final deleteConversationUrl = '$_baseEndpoint/v1/convos/$convoId';
    final response = await _oidcClient.delete(Uri.parse(deleteConversationUrl));
    if (response.statusCode != 204) {
      throw Exception(
        "Could not delete conversation with uuid '$convoId'. Status code: ${response.statusCode}",
      );
    }
  }

  @override
  Future<Map<String, dynamic>> getQuiz(String roomId, String quizId) async {
    final getQuizUrl = '$_baseEndpoint/v1/rooms/$roomId/quiz/$quizId';
    final response = await _oidcClient.get(Uri.parse(getQuizUrl));

    if (response.statusCode != 200) {
      throw Exception(
        'Could not retrieve quiz `$quizId`. Response code = ${response.statusCode}',
      );
    }

    final decoded = jsonDecode(response.body);
    return decoded;
  }

  @override
  Future<Map<String, dynamic>> getChatroomInformation({
    required String roomId,
    required Duration timeout,
  }) async {
    final chatroomInformationUrl = '$_baseEndpoint/v1/rooms/$roomId';

    final newConversationResponse = await _oidcClient.get(
      Uri.parse(chatroomInformationUrl),
    );

    if (newConversationResponse.statusCode != 200) {
      throw Exception(
        'Could not get chatroom information for `$roomId`. Response code = ${newConversationResponse.statusCode}',
      );
    }

    return jsonDecode(newConversationResponse.body) as Map<String, dynamic>;
  }

  @override
  Future<String> getChatroomPrompt({required String roomId}) async {
    final chatroomPromptUrl = '$_baseEndpoint/v1/rooms/$roomId/prompt';

    final promptResponse = await _oidcClient.get(Uri.parse(chatroomPromptUrl));

    if (promptResponse.statusCode != 200) {
      throw Exception(
        'Could not get chatroom prompt for `$roomId`. Response code = ${promptResponse.statusCode}',
      );
    }

    return promptResponse.body;
  }

  @override
  Future<Uint8List?> getChatroomBgImage({required String roomId}) async {
    final chatroomBgUrl = '$_baseEndpoint/v1/rooms/$roomId/bg_image';

    final bgImageResponse = await _oidcClient.get(Uri.parse(chatroomBgUrl));

    if (bgImageResponse.statusCode != 200) {
      debugPrint(
        'Could not get chatroom information for `$roomId`. Response code = ${bgImageResponse.statusCode}',
      );
      return null;
    }
    return bgImageResponse.bodyBytes;
  }

  @override
  Future<Map<String, dynamic>> getLoginSystems(Duration timeout) async {
    final loginSystemsUrl = '$_baseEndpoint/login';

    final loginSystemsResponse = await _oidcClient.getWithTimeout(
      Uri.parse(loginSystemsUrl),
      timeLimit: timeout,
    );

    if (loginSystemsResponse.statusCode != 200) {
      throw Exception(
        'Could not get login information. Response code = ${loginSystemsResponse.statusCode}',
      );
    }

    return jsonDecode(loginSystemsResponse.body) as Map<String, dynamic>;
  }

  @override
  Future<Map<String, dynamic>> getMcpToken(
    String roomId,
    Duration timeout,
  ) async {
    final mcpTokenUrl = '$_baseEndpoint/v1/rooms/$roomId/mcp_token';

    final mcpTokenResponse = await _oidcClient.getWithTimeout(
      Uri.parse(mcpTokenUrl),
      timeLimit: timeout,
    );

    if (mcpTokenResponse.statusCode != 200) {
      throw Exception(
        'Could not get login information. Response code = ${mcpTokenResponse.statusCode}',
      );
    }

    return jsonDecode(mcpTokenResponse.body) as Map<String, dynamic>;
  }

  @override
  Future<Map<String, dynamic>> getUserInfo(Duration timeout) async {
    final userInfoUrl = '$_baseEndpoint/get_user_info';

    final userInfoUrlResponse = await _oidcClient.getWithTimeout(
      Uri.parse(userInfoUrl),
      timeLimit: timeout,
    );

    if (userInfoUrlResponse.statusCode != 200) {
      throw Exception(
        'Could not get login information. Response code = ${userInfoUrlResponse.statusCode}',
      );
    }

    return jsonDecode(userInfoUrlResponse.body) as Map<String, dynamic>;
  }
}

class LocalChatroomProvider implements ChatroomProvider {
  final chatRooms = _buildChatRooms();
  final history = [
    {"origin": "user", "text": "This is the first message sent."},
    {"origin": "llm", "text": "This is the LLM response"},
  ];

  @override
  Future<List<String>> listAvailableChatrooms() async {
    final encoded = <String>[];
    for (final room in chatRooms) {
      encoded.add(jsonEncode({room.roomId: room.toJson()}));
    }
    return encoded;
  }

  @override
  Future<String> retrieveChatroom(String id) async {
    final roomConfig = chatRooms.firstWhere((e) => e.roomId == id);

    await Future.delayed(Duration(milliseconds: 500));
    return jsonEncode(roomConfig.toJson());
  }

  @override
  Future<Map<String, dynamic>> retrieveConversations() async {
    final roomConversations = <String, dynamic>{};

    for (int i = 0; i < chatRooms.length; i++) {
      roomConversations['FD$i-X5-FDS'] = {
        'name': chatRooms[i].welcomeMessage ?? 'Room $i',
        'room_id': chatRooms[i].roomId,
      };
    }
    return roomConversations;
  }

  static List<ChatroomConfig> _buildChatRooms() {
    final simpleChatroom = ChatroomConfig(
      roomId: 'sample',
      welcomeMessage: 'Soliplex client',
      enableAttachments: false,
    );

    final minimalChatroom = ChatroomConfig(roomId: 'minimal');

    final welcomeOnlyChatroom = ChatroomConfig(
      roomId: 'welcome_only',
      welcomeMessage: 'Welcome to Soliplex client chat',
    );

    final suggestionsOnlyChatroom = ChatroomConfig(
      roomId: 'suggestions_only',
      suggestions: [
        'What is Soliplex client?',
        'I\'m interested! Who do I contact?',
      ],
    );

    final enableAttachmentsChatroom = ChatroomConfig(
      roomId: 'attachments_enabled',
      welcomeMessage: 'You can send attachments from this room.',
      enableAttachments: true,
    );

    return [
      simpleChatroom,
      minimalChatroom,
      welcomeOnlyChatroom,
      suggestionsOnlyChatroom,
      enableAttachmentsChatroom,
    ];
  }

  @override
  Future<Map<String, dynamic>> startNewConversation(
    String roomId,
    String initialMessage,
    Duration timeout,
  ) async {
    // TODO: implement startNewConversation
    throw UnimplementedError();
  }

  @override
  Future<List<Map<String, dynamic>>> retrieveConversation(String convoId) {
    // TODO: implement retrieveConversation
    throw UnimplementedError();
  }

  @override
  Future<void> deleteConversation(String convoId) {
    // TODO: implement deleteConversation
    throw UnimplementedError();
  }

  @override
  Future<Map<String, dynamic>> getQuiz(String roomId, String quizId) {
    // TODO: implement getQuestions
    throw UnimplementedError();
  }

  @override
  Future<Map<String, dynamic>> getChatroomInformation({
    required String roomId,
    required Duration timeout,
  }) {
    // TODO: implement getChatroomInformation
    throw UnimplementedError();
  }

  @override
  Future<Uint8List?> getChatroomBgImage({required String roomId}) {
    // TODO: implement getChatroomBgImage
    throw UnimplementedError();
  }

  @override
  Future<Map<String, dynamic>> getLoginSystems(Duration timeout) {
    // TODO: implement getLoginSystems
    throw UnimplementedError();
  }

  @override
  Future<String> getChatroomPrompt({required String roomId}) {
    // TODO: implement getChatroomPrompt
    throw UnimplementedError();
  }

  @override
  Future<Map<String, dynamic>> getMcpToken(String roomId, Duration timeout) {
    // TODO: implement getMcpToken
    throw UnimplementedError();
  }

  @override
  Future<Map<String, dynamic>> getUserInfo(Duration timeout) {
    // TODO: implement getUserInfo
    throw UnimplementedError();
  }
}
