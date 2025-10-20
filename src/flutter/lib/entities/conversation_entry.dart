import 'package:json_annotation/json_annotation.dart';

part 'conversation_entry.g.dart';

@JsonSerializable()
class ConversationEntry {
  ConversationEntry({
    required this.uuid,
    required this.name,
    required this.roomId,
  });

  final String uuid;

  final String name;

  final String roomId;

  factory ConversationEntry.fromJson(Map<String, dynamic> json) =>
      _$ConversationEntryFromJson(json);

  Map<String, dynamic> toJson() => _$ConversationEntryToJson(this);
}
