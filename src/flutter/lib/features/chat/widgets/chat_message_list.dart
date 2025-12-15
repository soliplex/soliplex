import 'package:flutter/material.dart';

import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/features/chat/view_models/chat_message_view_model.dart';
import 'package:soliplex/features/chat/view_models/message_view_model_mapper.dart';
import 'package:soliplex/features/chat/widgets/chat_message_bubble.dart';
import 'package:soliplex/features/chat/widgets/chat_typing_indicator.dart';

/// Custom chat message list that replaces DashChat.
///
/// Provides:
/// - Reverse scrolling (newest at bottom)
/// - Auto-scroll when near bottom
/// - Typing indicator
/// - Direct ChatMessage access (no conversion layer)
class ChatMessageList extends StatefulWidget {
  const ChatMessageList({
    required this.messages,
    super.key,
    this.scrollController,
    this.maxBubbleWidth = double.infinity,
    this.onQuote,
    this.onToggleThinking,
    this.onToggleToolGroup,
    this.onGenUiEvent,
    this.welcomeWidget,
  });
  final List<ChatMessage> messages; // Still takes domain messages
  final ScrollController? scrollController;
  final double maxBubbleWidth;
  final void Function(String quotedText)? onQuote;
  final void Function(String messageId)? onToggleThinking;
  final void Function(String messageId)? onToggleToolGroup;
  final void Function(String eventName, Map<String, Object?> arguments)?
  onGenUiEvent;

  /// Optional widget to show at the top of the list (e.g., welcome card).
  /// This appears above all messages when the list is empty or has few
  /// messages.
  final Widget? welcomeWidget;

  @override
  State<ChatMessageList> createState() => _ChatMessageListState();
}

class _ChatMessageListState extends State<ChatMessageList> {
  late ScrollController _scrollController;
  bool _isNearBottom = true;
  List<ChatMessageViewModel> _viewModels = [];
  final MessageViewModelMapper _mapper = MessageViewModelMapper();

  // Threshold for "near bottom" detection (in pixels)
  static const double _nearBottomThreshold = 100;

  @override
  void initState() {
    super.initState();
    _scrollController = widget.scrollController ?? ScrollController();
    _scrollController.addListener(_onScroll);
    _mapMessagesToViewModels();
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

  /// Maps incoming ChatMessages to ViewModels.
  void _mapMessagesToViewModels() {
    _viewModels = widget.messages.map(_mapper.map).toList();
  }

  @override
  void didUpdateWidget(ChatMessageList oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.messages != oldWidget.messages) {
      // Re-map messages when the underlying list changes
      _mapMessagesToViewModels();
      // Auto-scroll when new messages arrive and we're near bottom
      if (widget.messages.length > oldWidget.messages.length && _isNearBottom) {
        _scrollToBottom();
      }
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
    // Determine if agent is typing from the view models
    final isAgentTyping = _viewModels.any(
      (vm) =>
          vm.user.id == ChatUser.agent.id &&
          (vm is TextMessageViewModel && vm.isStreaming),
    );

    // Calculate total item count: view models + typing indicator + welcome
    // widget
    final hasWelcome = widget.welcomeWidget != null;
    final baseCount = _viewModels.length + (isAgentTyping ? 1 : 0);
    final itemCount = baseCount + (hasWelcome ? 1 : 0);

    if (itemCount == 0) {
      return const Center(child: Text('No messages yet'));
    }

    return ListView.builder(
      controller: _scrollController,
      reverse: true, // Newest at bottom, natural chat scrolling
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      itemCount: itemCount,
      itemBuilder: (context, index) {
        // In reverse mode, index 0 is the bottom (newest)
        // If typing, index 0 shows typing indicator
        if (isAgentTyping && index == 0) {
          return const Padding(
            key: ValueKey('typing-indicator'),
            padding: EdgeInsets.only(bottom: 8),
            child: ChatTypingIndicator(),
          );
        }

        // Welcome widget appears at the top (highest index in reverse list)
        if (hasWelcome && index == itemCount - 1) {
          return Padding(
            key: const ValueKey('welcome-widget'),
            padding: const EdgeInsets.only(bottom: 8),
            child: widget.welcomeWidget,
          );
        }

        // Adjust index for view models (account for typing indicator)
        final viewModelIndex = isAgentTyping ? index - 1 : index;

        // Since list is reversed, we need to access view models from the end
        // index 0 (or 1 if typing) = last view model
        final actualIndex = _viewModels.length - 1 - viewModelIndex;

        if (actualIndex < 0 || actualIndex >= _viewModels.length) {
          return const SizedBox.shrink();
        }

        final viewModel = _viewModels[actualIndex];

        // Get previous/next view models for context (optional, for grouping)
        final previousViewModel = actualIndex > 0
            ? _viewModels[actualIndex - 1]
            : null;
        final nextViewModel = actualIndex < _viewModels.length - 1
            ? _viewModels[actualIndex + 1]
            : null;

        return Padding(
          key: viewModel.key, // Use ViewModel's key
          padding: const EdgeInsets.only(bottom: 8),
          child: ChatMessageBubble(
            viewModel: viewModel, // Pass ViewModel
            previousViewModel: previousViewModel,
            nextViewModel: nextViewModel,
            maxWidth: widget.maxBubbleWidth,
            onQuote: widget.onQuote,
            onToggleThinking:
                widget.onToggleThinking != null &&
                    viewModel is TextMessageViewModel
                ? () => widget.onToggleThinking!(viewModel.id)
                : null,
            onToggleToolGroup:
                widget.onToggleToolGroup != null &&
                    viewModel is ToolCallGroupViewModel
                ? () => widget.onToggleToolGroup!(viewModel.id)
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
    final estimatedPosition =
        (totalMessages - 1 - index) * 80.0; // Rough height

    animateTo(
      estimatedPosition,
      duration: const Duration(milliseconds: 200),
      curve: Curves.easeOut,
    );
  }
}
