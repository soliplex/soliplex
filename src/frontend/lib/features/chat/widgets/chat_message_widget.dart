import 'package:flutter/material.dart';
import 'package:soliplex_client/soliplex_client.dart';

/// Widget that displays a single chat message.
class ChatMessageWidget extends StatelessWidget {
  const ChatMessageWidget({
    required this.message,
    this.isStreaming = false,
    super.key,
  });

  final ChatMessage message;
  final bool isStreaming;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    if (message.user == ChatUser.system) {
      return _buildSystemMessage(theme);
    }

    final isUser = message.user == ChatUser.user;
    final text = switch (message) {
      TextMessage(:final text) => text,
      ErrorMessage(:final errorText) => errorText,
      _ => '',
    };

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
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: isUser
                    ? theme.colorScheme.primaryContainer
                    : theme.colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    text,
                    style: theme.textTheme.bodyLarge?.copyWith(
                      color: message is ErrorMessage
                          ? theme.colorScheme.error
                          : isUser
                              ? theme.colorScheme.onPrimaryContainer
                              : theme.colorScheme.onSurface,
                    ),
                  ),
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

  Widget _buildSystemMessage(ThemeData theme) {
    final text = switch (message) {
      TextMessage(:final text) => text,
      ErrorMessage(:final errorText) => errorText,
      _ => '',
    };

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
            text,
            textAlign: TextAlign.center,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ),
      ),
    );
  }

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
