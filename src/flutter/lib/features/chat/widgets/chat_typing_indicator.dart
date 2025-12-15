import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'package:soliplex/core/models/chat_models.dart';

/// Animated typing indicator shown when agent is processing.
///
/// Displays three pulsing dots with the agent avatar, styled
/// to match the chat bubble appearance.
class ChatTypingIndicator extends StatefulWidget {
  const ChatTypingIndicator({super.key});

  @override
  State<ChatTypingIndicator> createState() => _ChatTypingIndicatorState();
}

class _ChatTypingIndicatorState extends State<ChatTypingIndicator>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        // Agent avatar
        _AgentAvatar(),
        const SizedBox(width: 8),
        // Typing bubble
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: List.generate(3, (index) {
              return AnimatedBuilder(
                animation: _controller,
                builder: (context, child) {
                  // Stagger animations for each dot
                  final delay = index * 0.2;
                  final value = (_controller.value + delay) % 1.0;
                  // Pulse effect using sin wave
                  final pulse = (1 + math.sin(value * 2 * math.pi)) / 2;
                  final scale = 0.6 + (0.4 * pulse);
                  final opacity = 0.4 + (0.6 * pulse);

                  return Container(
                    margin: const EdgeInsets.symmetric(horizontal: 2),
                    width: 8 * scale,
                    height: 8 * scale,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: colorScheme.onSurfaceVariant.withAlpha(
                        (opacity * 255).round(),
                      ),
                    ),
                  );
                },
              );
            }),
          ),
        ),
        // Spacer to push bubble to left (agent side)
        const Spacer(),
      ],
    );
  }
}

/// Simple agent avatar for typing indicator and messages.
class _AgentAvatar extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return CircleAvatar(
      radius: 16,
      backgroundColor: colorScheme.secondaryContainer,
      child: Text(
        ChatUser.agent.firstName?.substring(0, 1) ?? 'A',
        style: TextStyle(
          color: colorScheme.onSecondaryContainer,
          fontSize: 14,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }
}

/// Reusable avatar widget for chat messages.
class ChatAvatar extends StatelessWidget {
  const ChatAvatar({required this.user, super.key, this.radius = 16});
  final ChatUser user;
  final double radius;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final isUser = user.id == ChatUser.user.id;

    return CircleAvatar(
      radius: radius,
      backgroundColor: isUser
          ? colorScheme.primaryContainer
          : colorScheme.secondaryContainer,
      child: Text(
        user.firstName?.substring(0, 1).toUpperCase() ?? '?',
        style: TextStyle(
          color: isUser
              ? colorScheme.onPrimaryContainer
              : colorScheme.onSecondaryContainer,
          fontSize: radius * 0.875,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }
}
