import 'package:flutter/material.dart';
import 'package:soliplex_client/soliplex_client.dart';

/// Widget that displays a single chat message.
///
/// Displays messages with role-based styling:
/// - User messages: Right-aligned with blue background
/// - Assistant messages: Left-aligned with grey background
/// - System messages: Centered with subtle styling
///
/// Shows a typing indicator when the message is currently streaming.
///
/// **AM3 Scope**: Simple text display only. Markdown rendering will be
/// added in AM4.
///
/// Example:
/// ```dart
/// ChatMessageWidget(
///   message: ChatMessage.text(
///     user: ChatUser.user,
///     text: 'Hello!',
///   ),
///   isStreaming: false,
/// )
/// ```
class ChatMessageWidget extends StatelessWidget {
  /// Creates a chat message widget.
  const ChatMessageWidget({
    required this.message,
    this.isStreaming = false,
    super.key,
  });

  /// The message to display.
  final ChatMessage message;

  /// Whether this message is currently streaming.
  final bool isStreaming;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    // System messages are centered
    if (message.user == ChatUser.system) {
      return _buildSystemMessage(context, theme);
    }

    // User and assistant messages are aligned based on role
    final isUser = message.user == ChatUser.user;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        mainAxisAlignment:
            isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Flexible(
            child: Container(
              constraints: const BoxConstraints(maxWidth: 600),
              padding: const EdgeInsets.symmetric(
                horizontal: 16,
                vertical: 12,
              ),
              decoration: BoxDecoration(
                color: isUser
                    ? theme.colorScheme.primaryContainer
                    : theme.colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Message text
                  if (message.text != null)
                    Text(
                      message.text!,
                      style: theme.textTheme.bodyLarge?.copyWith(
                        color: isUser
                            ? theme.colorScheme.onPrimaryContainer
                            : theme.colorScheme.onSurface,
                      ),
                    ),

                  // Error message
                  if (message.errorMessage != null)
                    Text(
                      message.errorMessage!,
                      style: theme.textTheme.bodyLarge?.copyWith(
                        color: theme.colorScheme.error,
                      ),
                    ),

                  // Streaming indicator
                  if (isStreaming) ...[
                    const SizedBox(height: 8),
                    _buildStreamingIndicator(theme),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Builds a system message (centered).
  Widget _buildSystemMessage(BuildContext context, ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Center(
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: theme.colorScheme.surfaceContainerHigh,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            message.errorMessage ?? message.text ?? '',
            textAlign: TextAlign.center,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ),
      ),
    );
  }

  /// Builds the typing indicator.
  Widget _buildStreamingIndicator(ThemeData theme) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          width: 16,
          height: 16,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            valueColor: AlwaysStoppedAnimation<Color>(
              theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        const SizedBox(width: 8),
        Text(
          'Typing...',
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
            fontStyle: FontStyle.italic,
          ),
        ),
      ],
    );
  }
}
