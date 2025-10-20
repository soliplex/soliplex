import 'chatroom_config.dart';
import 'conversation_entry.dart';
import 'quiz_config.dart';

class ChatroomWithConversations {
  ChatroomWithConversations({
    required this.config,
    required this.conversations,
    this.quizzes = const {},
  });

  final ChatroomConfig config;
  final List<ConversationEntry> conversations;
  final Map<String, QuizConfig> quizzes;
}
