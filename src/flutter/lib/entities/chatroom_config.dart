import 'package:json_annotation/json_annotation.dart';

import 'quiz_config.dart';

part 'chatroom_config.g.dart';

@JsonSerializable()
class ChatroomConfig {
  ChatroomConfig({
    required this.roomId,
    this.welcomeMessage,
    this.suggestions,
    this.enableAttachments,
    this.quizzes,
  });
  @JsonKey(name: 'id')
  final String roomId;

  @JsonKey(name: 'welcome_message')
  final String? welcomeMessage;

  final List<String>? suggestions;

  @JsonKey(name: 'enable_attachments')
  final bool? enableAttachments;

  final Map<String, QuizConfig>? quizzes;

  factory ChatroomConfig.fromJson(Map<String, dynamic> json) =>
      _$ChatroomConfigFromJson(json);

  Map<String, dynamic> toJson() => _$ChatroomConfigToJson(this);
}
