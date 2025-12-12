import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import '../../features/chat/widgets/feedback_dialog.dart';

/// Service for persisting message feedback to local storage.
///
/// Feedback is stored per-room in JSON files:
/// `{documents}/soliplex_feedback/{room_id}.json`
class FeedbackService {
  final String roomId;
  final Map<String, FeedbackResult> _feedbackCache = {};
  bool _loaded = false;

  FeedbackService({required this.roomId});

  /// Get feedback for a specific message.
  FeedbackResult? getFeedback(String messageId) {
    return _feedbackCache[messageId];
  }

  /// Check if a message has feedback.
  bool hasFeedback(String messageId) {
    return _feedbackCache.containsKey(messageId);
  }

  /// Save feedback for a message.
  Future<void> saveFeedback(FeedbackResult feedback) async {
    _feedbackCache[feedback.messageId] = feedback;
    await _persistFeedback();
  }

  /// Remove feedback for a message.
  Future<void> removeFeedback(String messageId) async {
    _feedbackCache.remove(messageId);
    await _persistFeedback();
  }

  /// Load feedback from disk.
  Future<void> loadFeedback() async {
    if (_loaded) return;

    try {
      final file = await _getFeedbackFile();
      if (await file.exists()) {
        final content = await file.readAsString();
        final json = jsonDecode(content) as Map<String, dynamic>;
        final feedbackList = json['feedback'] as List<dynamic>? ?? [];

        for (final item in feedbackList) {
          final map = item as Map<String, dynamic>;
          final feedback = FeedbackResult(
            rating: map['rating'] == 'positive'
                ? FeedbackRating.positive
                : FeedbackRating.negative,
            comment: map['comment'] as String?,
            messageId: map['messageId'] as String,
            timestamp: DateTime.parse(map['timestamp'] as String),
          );
          _feedbackCache[feedback.messageId] = feedback;
        }
      }
      _loaded = true;
    } catch (e) {
      debugPrint('FeedbackService: Error loading feedback: $e');
    }
  }

  /// Persist feedback to disk.
  Future<void> _persistFeedback() async {
    try {
      final file = await _getFeedbackFile();
      final json = {
        'roomId': roomId,
        'updatedAt': DateTime.now().toIso8601String(),
        'feedback': _feedbackCache.values.map((f) => f.toJson()).toList(),
      };
      await file.writeAsString(jsonEncode(json));
    } catch (e) {
      debugPrint('FeedbackService: Error saving feedback: $e');
    }
  }

  /// Get the feedback file for this room.
  Future<File> _getFeedbackFile() async {
    final directory = await getApplicationDocumentsDirectory();
    final feedbackDir = Directory('${directory.path}/soliplex_feedback');

    if (!await feedbackDir.exists()) {
      await feedbackDir.create(recursive: true);
    }

    return File('${feedbackDir.path}/$roomId.json');
  }

  /// Get all feedback for this room.
  List<FeedbackResult> getAllFeedback() {
    return _feedbackCache.values.toList();
  }
}

/// State for the feedback service provider.
class FeedbackState {
  final Map<String, FeedbackResult> feedback;
  final bool isLoaded;

  const FeedbackState({
    this.feedback = const {},
    this.isLoaded = false,
  });

  FeedbackState copyWith({
    Map<String, FeedbackResult>? feedback,
    bool? isLoaded,
  }) {
    return FeedbackState(
      feedback: feedback ?? this.feedback,
      isLoaded: isLoaded ?? this.isLoaded,
    );
  }
}

/// Notifier for managing feedback state.
class FeedbackNotifier extends StateNotifier<FeedbackState> {
  FeedbackService? _service;

  FeedbackNotifier() : super(const FeedbackState());

  /// Initialize the service for a room.
  Future<void> initialize(String roomId) async {
    _service = FeedbackService(roomId: roomId);
    await _service!.loadFeedback();
    state = FeedbackState(
      feedback: Map.from(_service!._feedbackCache),
      isLoaded: true,
    );
  }

  /// Get feedback for a message.
  FeedbackResult? getFeedback(String messageId) {
    return state.feedback[messageId];
  }

  /// Check if a message has feedback.
  bool hasFeedback(String messageId) {
    return state.feedback.containsKey(messageId);
  }

  /// Save feedback.
  Future<void> saveFeedback(FeedbackResult feedback) async {
    if (_service == null) return;

    await _service!.saveFeedback(feedback);
    state = state.copyWith(
      feedback: Map.from(_service!._feedbackCache),
    );
  }

  /// Remove feedback.
  Future<void> removeFeedback(String messageId) async {
    if (_service == null) return;

    await _service!.removeFeedback(messageId);
    state = state.copyWith(
      feedback: Map.from(_service!._feedbackCache),
    );
  }
}

/// Provider for feedback service.
final feedbackProvider =
    StateNotifierProvider<FeedbackNotifier, FeedbackState>((ref) {
  return FeedbackNotifier();
});
