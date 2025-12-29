import 'package:flutter/material.dart';

/// Feedback rating type.
enum FeedbackRating { positive, negative }

/// Result from the feedback dialog.
class FeedbackResult {
  FeedbackResult({
    required this.rating,
    required this.messageId,
    this.comment,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();
  final FeedbackRating rating;
  final String? comment;
  final String messageId;
  final DateTime timestamp;

  Map<String, dynamic> toJson() => {
    'rating': rating.name,
    'comment': comment,
    'messageId': messageId,
    'timestamp': timestamp.toIso8601String(),
  };
}

/// Dialog for collecting feedback on a message.
class FeedbackDialog extends StatefulWidget {
  const FeedbackDialog({
    required this.initialRating,
    required this.messageId,
    super.key,
  });
  final FeedbackRating initialRating;
  final String messageId;

  /// Show the feedback dialog and return the result.
  static Future<FeedbackResult?> show(
    BuildContext context, {
    required FeedbackRating initialRating,
    required String messageId,
  }) {
    return showDialog<FeedbackResult>(
      context: context,
      builder: (context) =>
          FeedbackDialog(initialRating: initialRating, messageId: messageId),
    );
  }

  @override
  State<FeedbackDialog> createState() => _FeedbackDialogState();
}

class _FeedbackDialogState extends State<FeedbackDialog> {
  late FeedbackRating _selectedRating;
  final TextEditingController _commentController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _selectedRating = widget.initialRating;
  }

  @override
  void dispose() {
    _commentController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isPositive = _selectedRating == FeedbackRating.positive;

    return AlertDialog(
      title: Row(
        children: [
          Icon(
            isPositive ? Icons.thumb_up : Icons.thumb_down,
            color: isPositive ? Colors.green : Colors.red,
          ),
          const SizedBox(width: 12),
          Text(isPositive ? 'What was good?' : 'What could be better?'),
        ],
      ),
      content: SizedBox(
        width: 400,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Rating toggle
            Row(
              children: [
                const Text('Rating: '),
                const SizedBox(width: 12),
                SegmentedButton<FeedbackRating>(
                  segments: const [
                    ButtonSegment(
                      value: FeedbackRating.positive,
                      icon: Icon(Icons.thumb_up_outlined),
                      label: Text('Good'),
                    ),
                    ButtonSegment(
                      value: FeedbackRating.negative,
                      icon: Icon(Icons.thumb_down_outlined),
                      label: Text('Bad'),
                    ),
                  ],
                  selected: {_selectedRating},
                  onSelectionChanged: (selection) {
                    setState(() {
                      _selectedRating = selection.first;
                    });
                  },
                ),
              ],
            ),
            const SizedBox(height: 16),
            // Comment field
            TextField(
              controller: _commentController,
              maxLines: 4,
              decoration: InputDecoration(
                hintText: isPositive
                    ? 'What made this response helpful? (optional)'
                    : 'How could this response be improved? (optional)',
                border: const OutlineInputBorder(),
                filled: true,
                fillColor: theme.colorScheme.surfaceContainerLow,
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () {
            final result = FeedbackResult(
              rating: _selectedRating,
              comment: _commentController.text.trim().isEmpty
                  ? null
                  : _commentController.text.trim(),
              messageId: widget.messageId,
            );
            Navigator.of(context).pop(result);
          },
          child: const Text('Submit'),
        ),
      ],
    );
  }
}
