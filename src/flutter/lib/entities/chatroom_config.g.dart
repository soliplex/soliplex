// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'chatroom_config.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

ChatroomConfig _$ChatroomConfigFromJson(Map<String, dynamic> json) =>
    ChatroomConfig(
      roomId: json['id'] as String,
      welcomeMessage: json['welcome_message'] as String?,
      suggestions: (json['suggestions'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList(),
      enableAttachments: json['enable_attachments'] as bool?,
      quizzes: (json['quizzes'] as Map<String, dynamic>?)?.map(
        (k, e) => MapEntry(k, QuizConfig.fromJson(e as Map<String, dynamic>)),
      ),
    );

Map<String, dynamic> _$ChatroomConfigToJson(ChatroomConfig instance) =>
    <String, dynamic>{
      'id': instance.roomId,
      'welcome_message': instance.welcomeMessage,
      'suggestions': instance.suggestions,
      'enable_attachments': instance.enableAttachments,
      'quizzes': instance.quizzes,
    };
