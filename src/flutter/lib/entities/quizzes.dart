import 'package:json_annotation/json_annotation.dart';

part 'quizzes.g.dart';

@JsonSerializable(explicitToJson: true)
class QuizEntry {
  @JsonKey(name: 'room_id')
  final String roomId;
  final String id;
  final String title;
  final bool randomize;
  @JsonKey(name: 'max_questions')
  final int maxQuestions;
  final List<Question> questions;

  QuizEntry({
    required this.roomId,
    required this.id,
    required this.title,
    required this.maxQuestions,
    required this.randomize,
    required this.questions,
  });

  factory QuizEntry.fromJson(Map<String, dynamic> json) =>
      _$QuizEntryFromJson(json);

  Map<String, dynamic> toJson() => _$QuizEntryToJson(this);
}

@JsonSerializable(explicitToJson: true)
class Question {
  final String inputs;
  @JsonKey(name: 'expected_output')
  final String expectedAnswer;
  final MetaData metadata;

  Question({
    required this.inputs,
    required this.expectedAnswer,
    required this.metadata,
  });

  factory Question.fromJson(Map<String, dynamic> json) =>
      _$QuestionFromJson(json);

  Map<String, dynamic> toJson() => _$QuestionToJson(this);
}

@JsonSerializable(explicitToJson: true)
class MetaData {
  final String type;
  final List<String> options;
  final String uuid;

  MetaData(this.type, this.options, this.uuid);

  factory MetaData.fromJson(Map<String, dynamic> json) =>
      _$MetaDataFromJson(json);

  Map<String, dynamic> toJson() => _$MetaDataToJson(this);
}

@JsonSerializable(explicitToJson: true)
class AnswerResponse {
  final String correct;
  @JsonKey(name: 'expected_output')
  final String? expectedAnswer;

  AnswerResponse(this.correct, this.expectedAnswer);

  factory AnswerResponse.fromJson(Map<String, dynamic> json) =>
      _$AnswerResponseFromJson(json);

  Map<String, dynamic> toJson() => _$AnswerResponseToJson(this);
}
