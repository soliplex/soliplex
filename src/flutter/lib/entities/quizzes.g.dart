// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'quizzes.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

QuizEntry _$QuizEntryFromJson(Map<String, dynamic> json) => QuizEntry(
  roomId: json['room_id'] as String,
  id: json['id'] as String,
  title: json['title'] as String,
  maxQuestions: (json['max_questions'] as num).toInt(),
  randomize: json['randomize'] as bool,
  questions: (json['questions'] as List<dynamic>)
      .map((e) => Question.fromJson(e as Map<String, dynamic>))
      .toList(),
);

Map<String, dynamic> _$QuizEntryToJson(QuizEntry instance) => <String, dynamic>{
  'room_id': instance.roomId,
  'id': instance.id,
  'title': instance.title,
  'randomize': instance.randomize,
  'max_questions': instance.maxQuestions,
  'questions': instance.questions.map((e) => e.toJson()).toList(),
};

Question _$QuestionFromJson(Map<String, dynamic> json) => Question(
  inputs: json['inputs'] as String,
  expectedAnswer: json['expected_output'] as String,
  metadata: MetaData.fromJson(json['metadata'] as Map<String, dynamic>),
);

Map<String, dynamic> _$QuestionToJson(Question instance) => <String, dynamic>{
  'inputs': instance.inputs,
  'expected_output': instance.expectedAnswer,
  'metadata': instance.metadata.toJson(),
};

MetaData _$MetaDataFromJson(Map<String, dynamic> json) => MetaData(
  json['type'] as String,
  (json['options'] as List<dynamic>).map((e) => e as String).toList(),
  json['uuid'] as String,
);

Map<String, dynamic> _$MetaDataToJson(MetaData instance) => <String, dynamic>{
  'type': instance.type,
  'options': instance.options,
  'uuid': instance.uuid,
};

AnswerResponse _$AnswerResponseFromJson(Map<String, dynamic> json) =>
    AnswerResponse(
      json['correct'] as String,
      json['expected_output'] as String?,
    );

Map<String, dynamic> _$AnswerResponseToJson(AnswerResponse instance) =>
    <String, dynamic>{
      'correct': instance.correct,
      'expected_output': instance.expectedAnswer,
    };
