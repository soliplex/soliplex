import 'package:json_annotation/json_annotation.dart';

part 'quiz_config.g.dart';

@JsonSerializable(explicitToJson: true)
class QuizConfig {
  final String id;
  final String title;

  QuizConfig({required this.id, required this.title});

  factory QuizConfig.fromJson(Map<String, dynamic> json) =>
      _$QuizConfigFromJson(json);

  Map<String, dynamic> toJson() => _$QuizConfigToJson(this);
}
