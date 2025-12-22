import 'package:flutter/material.dart';

/// A button that triggers creation of a new conversation thread.
///
/// Displays as a prominent list item at the top of the history panel.
/// When pressed, signals intent to create a new thread.
///
/// Example:
/// ```dart
/// NewConversationButton(
///   onPressed: () {
///     ref.read(threadSelectionProvider.notifier).state =
///         const NewThreadIntent();
///   },
/// )
/// ```
class NewConversationButton extends StatelessWidget {
  /// Creates a new conversation button.
  const NewConversationButton({
    required this.onPressed,
    super.key,
  });

  /// Callback when the button is pressed.
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Material(
        color: colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(12),
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
            child: Row(
              children: [
                ExcludeSemantics(
                  child: Icon(
                    Icons.edit_outlined,
                    color: colorScheme.onPrimaryContainer,
                    size: 24,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Text(
                    'New Conversation',
                    style: theme.textTheme.titleMedium?.copyWith(
                      color: colorScheme.onPrimaryContainer,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                ExcludeSemantics(
                  child: Icon(
                    Icons.arrow_forward_ios,
                    color:
                        colorScheme.onPrimaryContainer.withValues(alpha: 0.5),
                    size: 16,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
