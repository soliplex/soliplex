// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'conversation_entry.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

ConversationEntry _$ConversationEntryFromJson(Map<String, dynamic> json) =>
    ConversationEntry(
      uuid: json['uuid'] as String,
      name: json['name'] as String,
      roomId: json['roomId'] as String,
    );

Map<String, dynamic> _$ConversationEntryToJson(ConversationEntry instance) =>
    <String, dynamic>{
      'uuid': instance.uuid,
      'name': instance.name,
      'roomId': instance.roomId,
    };
