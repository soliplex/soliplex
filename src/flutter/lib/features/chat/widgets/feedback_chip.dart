import 'package:flutter/material.dart';

import 'package:soliplex/features/chat/widgets/feedback_dialog.dart';

/// Model for FeedbackChip presentation state.
class FeedbackChipModel {
  const FeedbackChipModel({this.currentRating, this.comment});
  final FeedbackRating? currentRating;
  final String? comment;

  bool get isThumbsUpSelected => currentRating == FeedbackRating.positive;
  bool get isThumbsDownSelected => currentRating == FeedbackRating.negative;
  bool get hasComment => comment != null && comment!.isNotEmpty;
}

/// Pure presentation feedback chip component.
///
/// Displays thumbs up/down buttons and optional comment indicator.
/// All state management and business logic is handled externally via callbacks.
class FeedbackChip extends StatelessWidget {
  const FeedbackChip({
    required this.model,
    required this.onThumbsUp,
    required this.onThumbsDown,
    super.key,
  });
  final FeedbackChipModel model;
  final VoidCallback onThumbsUp;
  final VoidCallback onThumbsDown;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _FeedbackButton(
            icon: Icons.thumb_up_outlined,
            selectedIcon: Icons.thumb_up,
            isSelected: model.isThumbsUpSelected,
            color: Colors.green,
            tooltip: 'Good response',
            onPressed: onThumbsUp,
          ),
          const SizedBox(width: 4),
          _FeedbackButton(
            icon: Icons.thumb_down_outlined,
            selectedIcon: Icons.thumb_down,
            isSelected: model.isThumbsDownSelected,
            color: Colors.red,
            tooltip: 'Bad response',
            onPressed: onThumbsDown,
          ),
          if (model.hasComment) ...[
            const SizedBox(width: 8),
            Tooltip(
              message: model.comment,
              child: Icon(
                Icons.comment_outlined,
                size: 14,
                color: theme.colorScheme.outline,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Individual feedback button (thumbs up or down).
class _FeedbackButton extends StatelessWidget {
  const _FeedbackButton({
    required this.icon,
    required this.selectedIcon,
    required this.isSelected,
    required this.color,
    required this.tooltip,
    required this.onPressed,
  });
  final IconData icon;
  final IconData selectedIcon;
  final bool isSelected;
  final Color color;
  final String tooltip;
  final VoidCallback onPressed;

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
