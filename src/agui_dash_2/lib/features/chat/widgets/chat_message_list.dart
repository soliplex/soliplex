import 'package:flutter/material.dart';

import '../../../core/models/chat_models.dart';
import 'chat_message_bubble.dart';
import 'chat_typing_indicator.dart';

/// Custom chat message list that replaces DashChat.
///
/// Provides:
/// - Reverse scrolling (newest at bottom)
/// - Auto-scroll when near bottom
/// - Typing indicator
/// - Direct ChatMessage access (no conversion layer)
class ChatMessageList extends StatefulWidget {
  final List<ChatMessage> messages;
  final bool isAgentTyping;
  final ScrollController? scrollController;
  final double maxBubbleWidth;
  final void Function(String quotedText)? onQuote;
  final void Function(String messageId)? onToggleThinking;
  final void Function(String messageId)? onToggleToolGroup;
  final void Function(String eventName, Map<String, Object?> arguments)? onGenUiEvent;

  const ChatMessageList({
    super.key,
    required this.messages,
    this.isAgentTyping = false,
    this.scrollController,
    this.maxBubbleWidth = double.infinity,
    this.onQuote,
    this.onToggleThinking,
    this.onToggleToolGroup,
    this.onGenUiEvent,
  });

  @override
  State<ChatMessageList> createState() => _ChatMessageListState();
}

class _ChatMessageListState extends State<ChatMessageList> {
  late ScrollController _scrollController;
  bool _isNearBottom = true;

  // Threshold for "near bottom" detection (in pixels)
  static const double _nearBottomThreshold = 100;

  @override
  void initState() {
    super.initState();
    _scrollController = widget.scrollController ?? ScrollController();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    if (widget.scrollController == null) {
      _scrollController.dispose();
    } else {
      _scrollController.removeListener(_onScroll);
    }
    super.dispose();
  }

  @override
  void didUpdateWidget(ChatMessageList oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Auto-scroll when new messages arrive and we're near bottom
    if (widget.messages.length > oldWidget.messages.length && _isNearBottom) {
      _scrollToBottom();
    }
  }

  void _onScroll() {
    // For reverse list, "near bottom" means near offset 0
    final isNear = _scrollController.offset < _nearBottomThreshold;
    if (isNear != _isNearBottom) {
      setState(() => _isNearBottom = isNear);
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          0, // For reverse list, 0 is the bottom
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    // Calculate total item count: messages + typing indicator if active
    final itemCount = widget.messages.length + (widget.isAgentTyping ? 1 : 0);

    if (itemCount == 0) {
      return const Center(
        child: Text('No messages yet'),
      );
    }

    return ListView.builder(
      controller: _scrollController,
      reverse: true, // Newest at bottom, natural chat scrolling
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      itemCount: itemCount,
      itemBuilder: (context, index) {
        // In reverse mode, index 0 is the bottom (newest)
        // If typing, index 0 shows typing indicator
        if (widget.isAgentTyping && index == 0) {
          return const Padding(
            padding: EdgeInsets.only(bottom: 8),
            child: ChatTypingIndicator(),
          );
        }

        // Adjust index for messages (account for typing indicator)
        final messageIndex = widget.isAgentTyping ? index - 1 : index;

        // Since list is reversed, we need to access messages from the end
        // index 0 (or 1 if typing) = last message
        final actualIndex = widget.messages.length - 1 - messageIndex;

        if (actualIndex < 0 || actualIndex >= widget.messages.length) {
          return const SizedBox.shrink();
        }

        final message = widget.messages[actualIndex];

        // Get previous/next messages for context (optional, for grouping)
        final previousMessage = actualIndex > 0
            ? widget.messages[actualIndex - 1]
            : null;
        final nextMessage = actualIndex < widget.messages.length - 1
            ? widget.messages[actualIndex + 1]
            : null;

        return Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: ChatMessageBubble(
            message: message,
            previousMessage: previousMessage,
            nextMessage: nextMessage,
            maxWidth: widget.maxBubbleWidth,
            onQuote: widget.onQuote,
            onToggleThinking: widget.onToggleThinking != null
                ? () => widget.onToggleThinking!(message.id)
                : null,
            onToggleToolGroup: widget.onToggleToolGroup != null
                ? () => widget.onToggleToolGroup!(message.id)
                : null,
            onGenUiEvent: widget.onGenUiEvent,
          ),
        );
      },
    );
  }
}

/// Scroll-to-message extension for search functionality.
extension ChatMessageListScrolling on ScrollController {
  /// Scroll to bring a specific message index into view.
  ///
  /// Note: For reverse lists, this requires calculating the position.
  /// The index should be from the original (non-reversed) message list.
  void scrollToMessageIndex(int index, int totalMessages) {
    if (!hasClients) return;

    // Estimate position (rough calculation - may need refinement)
    // For a more accurate approach, we'd need itemExtent or key-based scrolling
    final estimatedPosition = (totalMessages - 1 - index) * 80.0; // Rough height

    animateTo(
      estimatedPosition,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeOut,
    );
  }
}
