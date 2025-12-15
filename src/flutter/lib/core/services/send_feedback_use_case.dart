import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex/core/services/feedback_service.dart';
import 'package:soliplex/features/chat/widgets/feedback_chip.dart';
import 'package:soliplex/features/chat/widgets/feedback_dialog.dart';

/// Use case for handling feedback submission flow.
///
/// Encapsulates the business logic for:
/// - Showing feedback dialog
/// - Saving/removing feedback
/// - Building presentation model from state
class SendFeedbackUseCase {
  SendFeedbackUseCase(this._ref);
  final Ref _ref;

  /// Handle thumbs up/down tap.
  ///
  /// If the same rating is already selected, removes feedback.
  /// Otherwise shows the feedback dialog.
  Future<void> handleFeedbackTap({
    required BuildContext context,
    required String messageId,
    required FeedbackRating rating,
  }) async {
    final notifier = _ref.read(feedbackProvider.notifier);
    final existingFeedback = notifier.getFeedback(messageId);

    // If clicking the same rating that's already selected, remove feedback
    if (existingFeedback?.rating == rating) {
      await notifier.removeFeedback(messageId);
      return;
    }

    // Show dialog to collect feedback
    final result = await FeedbackDialog.show(
      context,
      initialRating: rating,
      messageId: messageId,
    );

    if (result != null) {
      await notifier.saveFeedback(result);
    }
  }

  /// Build a FeedbackChipModel from current state.
  FeedbackChipModel buildModel(String messageId) {
    final feedbackState = _ref.read(feedbackProvider);
    final existingFeedback = feedbackState.feedback[messageId];

    return FeedbackChipModel(
      currentRating: existingFeedback?.rating,
      comment: existingFeedback?.comment,
    );
  }
}

/// Provider for SendFeedbackUseCase.
final sendFeedbackUseCaseProvider = Provider<SendFeedbackUseCase>((ref) {
  return SendFeedbackUseCase(ref);
});
