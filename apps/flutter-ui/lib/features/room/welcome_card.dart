import 'package:flutter/material.dart';

import 'package:soliplex/core/models/room_models.dart';
import 'package:soliplex/features/chat/widgets/suggestion_chip.dart';

/// An animated welcome card displayed when entering a room with no messages.
///
/// Shows the room's welcome message and description with a fade-in and
/// scale animation. Includes suggestion chips if available.
class WelcomeCard extends StatefulWidget {
  const WelcomeCard({
    required this.room,
    super.key,
    this.onDismiss,
    this.onSuggestionTap,
  });
  final Room room;
  final VoidCallback? onDismiss;
  final void Function(String suggestion)? onSuggestionTap;

  @override
  State<WelcomeCard> createState() => _WelcomeCardState();
}

class _WelcomeCardState extends State<WelcomeCard>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _fadeAnimation;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 400),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(
      begin: 0,
      end: 1,
    ).animate(CurvedAnimation(parent: _controller, curve: Curves.easeOut));

    _scaleAnimation = Tween<double>(
      begin: 0.95,
      end: 1,
    ).animate(CurvedAnimation(parent: _controller, curve: Curves.easeOut));

    _controller.forward();
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

    final welcomeText = widget.room.effectiveWelcomeMessage;
    final hasWelcome = welcomeText != null && welcomeText.isNotEmpty;
    final hasSuggestions = widget.room.suggestions.isNotEmpty;

    if (!hasWelcome && !hasSuggestions) {
      return const SizedBox.shrink();
    }

    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return FadeTransition(
          opacity: _fadeAnimation,
          child: ScaleTransition(scale: _scaleAnimation, child: child),
        );
      },
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Card(
          elevation: 0,
          color: colorScheme.primaryContainer.withValues(alpha: 0.3),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: BorderSide(color: colorScheme.primaryContainer),
          ),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                // Header row with icon and room name
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: colorScheme.primary.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Icon(
                        Icons.waving_hand_rounded,
                        color: colorScheme.primary,
                        size: 24,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Welcome to ${widget.room.name}',
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w600,
                              color: colorScheme.onSurface,
                            ),
                          ),
                          if (widget.room.agent?.displayModelName != null)
                            Text(
                              widget.room.agent!.displayModelName,
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: colorScheme.onSurfaceVariant,
                              ),
                            ),
                        ],
                      ),
                    ),
                    if (widget.onDismiss != null)
                      IconButton(
                        icon: Icon(
                          Icons.close,
                          size: 18,
                          color: colorScheme.onSurfaceVariant,
                        ),
                        onPressed: widget.onDismiss,
                        tooltip: 'Dismiss',
                      ),
                  ],
                ),

                // Welcome message
                if (hasWelcome) ...[
                  const SizedBox(height: 12),
                  Text(
                    welcomeText,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],

                // Suggestion chips
                if (hasSuggestions) ...[
                  const SizedBox(height: 16),
                  Text(
                    'Try asking:',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: widget.room.suggestions.map((suggestion) {
                      return SuggestionChip.welcome(
                        text: suggestion,
                        onTap: () => widget.onSuggestionTap?.call(suggestion),
                      );
                    }).toList(),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
