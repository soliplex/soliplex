import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'package:soliplex/core/models/room_models.dart';
import 'package:soliplex/features/room/suggestion_chips.dart';
import 'package:soliplex/features/room/welcome_card.dart';

/// Custom chat input area with integrated suggestions.
///
/// Replaces DashChat's built-in input to properly position suggestions
/// above the text field, avoiding layout conflicts with the message list.
class ChatInputArea extends StatefulWidget {
  const ChatInputArea({
    required this.controller,
    required this.onSend,
    super.key,
    this.room,
    this.hasMessages = false,
    this.isLoading = false,
    this.onSuggestionTap,
    this.showWelcome = true,
    this.showSuggestions = true,
    this.focusNode,
  });
  final TextEditingController controller;
  final VoidCallback onSend;
  final Room? room;
  final bool hasMessages;
  final bool isLoading;
  final void Function(String)? onSuggestionTap;

  /// Whether to show the welcome card (when no messages).
  final bool showWelcome;

  /// Whether to show suggestion chips (when has messages).
  final bool showSuggestions;

  /// Focus node for the input field (optional, creates one if not provided).
  final FocusNode? focusNode;

  @override
  State<ChatInputArea> createState() => _ChatInputAreaState();
}

class _ChatInputAreaState extends State<ChatInputArea> {
  FocusNode? _ownedFocusNode;

  FocusNode get _focusNode =>
      widget.focusNode ?? (_ownedFocusNode ??= FocusNode());

  @override
  void dispose() {
    _ownedFocusNode?.dispose();
    super.dispose();
  }

  void _handleSubmit() {
    final text = widget.controller.text.trim();
    if (text.isEmpty) return;
    widget.onSend();
  }

  /// Handle suggestion tap - fills input and auto-submits.
  void _handleSuggestionTap(String suggestion) {
    widget.controller.text = suggestion;
    widget.controller.selection = TextSelection.collapsed(
      offset: suggestion.length,
    );
    widget.onSuggestionTap?.call(suggestion);
    // Auto-submit the suggestion
    widget.onSend();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final hasSuggestions = widget.room?.suggestions.isNotEmpty ?? false;

    return Container(
      decoration: BoxDecoration(
        color: colorScheme.surface,
        border: Border(
          top: BorderSide(color: colorScheme.outline.withValues(alpha: 0.1)),
        ),
      ),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Welcome card (shown when no messages)
            if (widget.showWelcome &&
                !widget.hasMessages &&
                widget.room != null)
              WelcomeCard(
                room: widget.room!,
                onSuggestionTap: _handleSuggestionTap,
              ),

            // Suggestion chips (shown when has messages and suggestions)
            if (widget.showSuggestions &&
                widget.hasMessages &&
                hasSuggestions &&
                !widget.isLoading)
              _SuggestionsSection(
                suggestions: widget.room!.suggestions,
                onTap: _handleSuggestionTap,
              ),

            // Input row
            Padding(
              padding: const EdgeInsets.all(8),
              child: _InputRow(
                controller: widget.controller,
                focusNode: _focusNode,
                onSubmit: _handleSubmit,
                isLoading: widget.isLoading,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Suggestions section above input.
class _SuggestionsSection extends StatelessWidget {
  const _SuggestionsSection({required this.suggestions, required this.onTap});
  final List<String> suggestions;
  final void Function(String) onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 16, top: 8, bottom: 4),
          child: Text(
            'Suggestions',
            style: theme.textTheme.labelSmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
              fontWeight: FontWeight.w500,
            ),
          ),
        ),
        SuggestionChips(suggestions: suggestions, onSuggestionTap: onTap),
      ],
    );
  }
}

/// Input row with text field and send button.
class _InputRow extends StatelessWidget {
  const _InputRow({
    required this.controller,
    required this.focusNode,
    required this.onSubmit,
    this.isLoading = false,
  });
  final TextEditingController controller;
  final FocusNode focusNode;
  final VoidCallback onSubmit;
  final bool isLoading;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        // Text field
        Expanded(
          child: KeyboardListener(
            focusNode: FocusNode(),
            onKeyEvent: (event) {
              // Handle Enter to send (Shift+Enter for newline)
              if (event is KeyDownEvent &&
                  event.logicalKey == LogicalKeyboardKey.enter &&
                  !HardwareKeyboard.instance.isShiftPressed) {
                onSubmit();
              }
            },
            child: TextField(
              controller: controller,
              focusNode: focusNode,
              enabled: !isLoading,
              maxLines: 5,
              minLines: 1,
              textInputAction: TextInputAction.newline,
              decoration: InputDecoration(
                hintText: 'Type a message, SHIFT+ENTER for multiple lines',
                filled: true,
                fillColor: colorScheme.surfaceContainerHighest,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide.none,
                ),
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 20,
                  vertical: 12,
                ),
              ),
              style: theme.textTheme.bodyMedium,
            ),
          ),
        ),
        const SizedBox(width: 8),
        // Send button
        IconButton(
          onPressed: isLoading ? null : onSubmit,
          icon: const Icon(Icons.send),
          color: colorScheme.primary,
          tooltip: 'Send message',
        ),
      ],
    );
  }
}

/// Activity status bar shown during agent processing.
///
/// Replaces the input area while the agent is working.
class ActivityStatusBar extends StatelessWidget {
  const ActivityStatusBar({required this.message, super.key, this.onStop});
  final String message;
  final VoidCallback? onStop;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Container(
      decoration: BoxDecoration(
        color: colorScheme.surface,
        border: Border(
          top: BorderSide(color: colorScheme.outline.withValues(alpha: 0.1)),
        ),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: Container(
            constraints: const BoxConstraints(minHeight: 48),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(24),
            ),
            child: Row(
              children: [
                // Pulsing dots
                const _ActivityDots(),
                const SizedBox(width: 8),
                // Status message with animation
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 300),
                  switchInCurve: Curves.easeOut,
                  switchOutCurve: Curves.easeIn,
                  transitionBuilder: (child, animation) {
                    return FadeTransition(
                      opacity: animation,
                      child: SlideTransition(
                        position: Tween<Offset>(
                          begin: const Offset(0, 0.3),
                          end: Offset.zero,
                        ).animate(animation),
                        child: child,
                      ),
                    );
                  },
                  child: Text(
                    message,
                    key: ValueKey(message),
                    style: TextStyle(
                      color: colorScheme.onSurfaceVariant,
                      fontSize: 14,
                    ),
                  ),
                ),
                const Spacer(),
                // Stop button
                if (onStop != null)
                  IconButton(
                    icon: const Icon(Icons.stop_circle_outlined),
                    onPressed: onStop,
                    tooltip: 'Stop generation',
                    color: colorScheme.error,
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Pulsing dots animation for activity indicator.
class _ActivityDots extends StatefulWidget {
  const _ActivityDots();

  @override
  State<_ActivityDots> createState() => _ActivityDotsState();
}

class _ActivityDotsState extends State<_ActivityDots>
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
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(3, (index) {
        return AnimatedBuilder(
          animation: _controller,
          builder: (context, child) {
            // Stagger the animations for each dot
            final delay = index * 0.2;
            final value = (_controller.value + delay) % 1.0;
            // Pulse effect using sin wave
            final pulse = (1 + _sin(value * 2 * 3.14159)) / 2;
            final scale = 0.5 + (0.5 * pulse);
            final opacity = 0.4 + (0.6 * pulse);

            return Container(
              margin: const EdgeInsets.symmetric(horizontal: 2),
              width: 6 * scale,
              height: 6 * scale,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Theme.of(
                  context,
                ).colorScheme.primary.withAlpha((opacity * 255).round()),
              ),
            );
          },
        );
      }),
    );
  }

  /// Simple sin approximation using Taylor series.
  double _sin(double value) {
    var calculatedValue = value;
    calculatedValue = calculatedValue % (2 * 3.14159);
    if (calculatedValue > 3.14159) calculatedValue -= 2 * 3.14159;
    var result = calculatedValue;
    var term = calculatedValue;
    for (var i = 1; i <= 5; i++) {
      term *= -calculatedValue * calculatedValue / ((2 * i) * (2 * i + 1));
      result += term;
    }
    return result;
  }
}
