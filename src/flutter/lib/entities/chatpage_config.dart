import 'dart:typed_data';

import 'package:flutter_ai_toolkit/flutter_ai_toolkit.dart';

import 'chatroom_config.dart';

class ChatpageConfig {
  ChatpageConfig({
    required this.roomConfig,
    required this.initialMessages,
    required this.bgImageData,
  });

  ChatroomConfig roomConfig;
  List<ChatMessage> initialMessages;
  Uint8List? bgImageData;
}
