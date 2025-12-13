import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/services/feedback_service.dart';
import 'feedback_dialog.dart';

/// Feedback chips displayed below assistant messages.
///
/// Shows thumbs up/down buttons that open a feedback dialog when clicked.
/// If feedback has already been submitted, shows the selected rating.
class MessageFeedbackChips extends ConsumerWidget {
  final String messageId;

  const MessageFeedbackChips({super.key, required this.messageId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final feedbackState = ref.watch(feedbackProvider);
    final existingFeedback = feedbackState.feedback[messageId];

    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _FeedbackButton(
            icon: Icons.thumb_up_outlined,
            selectedIcon: Icons.thumb_up,
            isSelected: existingFeedback?.rating == FeedbackRating.positive,
            color: Colors.green,
            tooltip: 'Good response',
            onPressed: () => _handleFeedback(
              context,
              ref,
              FeedbackRating.positive,
              existingFeedback,
            ),
          ),
          const SizedBox(width: 4),
          _FeedbackButton(
            icon: Icons.thumb_down_outlined,
            selectedIcon: Icons.thumb_down,
            isSelected: existingFeedback?.rating == FeedbackRating.negative,
            color: Colors.red,
            tooltip: 'Bad response',
            onPressed: () => _handleFeedback(
              context,
              ref,
              FeedbackRating.negative,
              existingFeedback,
            ),
          ),
          // Show indicator if feedback was submitted with a comment
          if (existingFeedback?.comment != null) ...[
            const SizedBox(width: 8),
            Tooltip(
              message: existingFeedback!.comment!,
              child: Icon(
                Icons.comment_outlined,
                size: 14,
                color: Theme.of(context).colorScheme.outline,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _handleFeedback(
    BuildContext context,
    WidgetRef ref,
    FeedbackRating rating,
    FeedbackResult? existingFeedback,
  ) async {
    // If clicking the same rating that's already selected, remove feedback
    if (existingFeedback?.rating == rating) {
      await ref.read(feedbackProvider.notifier).removeFeedback(messageId);
      return;
    }

    // Show dialog to collect feedback
    final result = await FeedbackDialog.show(
      context,
      initialRating: rating,
      messageId: messageId,
    );

    if (result != null) {
      await ref.read(feedbackProvider.notifier).saveFeedback(result);
    }
  }
}

/// Individual feedback button (thumbs up or down).
class _FeedbackButton extends StatelessWidget {
  final IconData icon;
  final IconData selectedIcon;
  final bool isSelected;
  final Color color;
  final String tooltip;
  final VoidCallback onPressed;

  const _FeedbackButton({
    required this.icon,
    required this.selectedIcon,
    required this.isSelected,
    required this.color,
    required this.tooltip,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: InkWell(
        onTap: onPressed,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(6),
          child: Icon(
            isSelected ? selectedIcon : icon,
            size: 16,
            color: isSelected ? color : Theme.of(context).colorScheme.outline,
          ),
        ),
      ),
    );
  }
}
