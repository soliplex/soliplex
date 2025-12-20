import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/models/chat_models.dart'; // For ChatUser, GenUiContent, ChatErrorInfo
import 'package:soliplex/core/models/error_types.dart';
import 'package:soliplex/core/services/feedback_service.dart';
import 'package:soliplex/core/services/send_feedback_use_case.dart';
import 'package:soliplex/core/services/send_to_canvas_use_case.dart';
import 'package:soliplex/features/chat/view_models/chat_message_view_model.dart'; // Import ViewModels
import 'package:soliplex/features/chat/widgets/chat_typing_indicator.dart';
import 'package:soliplex/features/chat/widgets/collapsible_citations_widget.dart';
import 'package:soliplex/features/chat/widgets/collapsible_thinking_widget.dart';
import 'package:soliplex/features/chat/widgets/feedback_chip.dart';
import 'package:soliplex/features/chat/widgets/feedback_dialog.dart';
import 'package:soliplex/features/chat/widgets/friendly_error_card.dart';
import 'package:soliplex/features/chat/widgets/genui_message_widget.dart';
import 'package:soliplex/features/chat/widgets/streaming_markdown_widget.dart';
import 'package:soliplex/features/chat/widgets/tool_call_summary_widget.dart';

/// Message bubble that handles all message types directly.
///
/// Replaces DashChat's message rendering with direct ChatMessage → Widget
/// routing.
/// No conversion layer needed.
class ChatMessageBubble extends ConsumerWidget {
  const ChatMessageBubble({
    required this.viewModel,
    required this.roomId,
    super.key,
    this.previousViewModel,
    this.nextViewModel,
    this.maxWidth = double.infinity,
    this.onQuote,
    this.onToggleThinking,
    this.onToggleCitations,
    this.onToggleToolGroup,
    this.onGenUiEvent,
  });
  final ChatMessageViewModel viewModel; // Now takes a ViewModel
  final ChatMessageViewModel? previousViewModel;
  final ChatMessageViewModel? nextViewModel;
  final double maxWidth;
  final String roomId;
  final void Function(String quotedText)? onQuote;
  final VoidCallback? onToggleThinking;
  final VoidCallback? onToggleCitations;
  final VoidCallback? onToggleToolGroup;
  final void Function(String eventName, Map<String, Object?> arguments)?
  onGenUiEvent;

  bool get _isUser => viewModel.user.id == ChatUser.user.id;
  bool get _isAgent => viewModel.user.id == ChatUser.agent.id;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    // Determine if we should show avatar (first message from this user in a
    // group)
    // Check if previousViewModel is from the same user.
    final showAvatar = previousViewModel?.user.id != viewModel.user.id;

    return Row(
      mainAxisAlignment: _isUser
          ? MainAxisAlignment.end
          : MainAxisAlignment.start,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        // Agent avatar (left side)
        if (!_isUser && showAvatar)
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: ChatAvatar(user: viewModel.user),
          )
        else if (!_isUser)
          const SizedBox(width: 40), // Spacer for alignment
        // Message content
        Flexible(
          child: ConstrainedBox(
            constraints: BoxConstraints(maxWidth: maxWidth),
            child: _buildContent(context, colorScheme),
          ),
        ),

        // User avatar (right side) - optional, currently not shown
        if (_isUser) const SizedBox(width: 8),
      ],
    );
  }

  Widget _buildContent(BuildContext context, ColorScheme colorScheme) {
    // Route to appropriate builder based on ViewModel type
    return switch (viewModel) {
      final TextMessageViewModel vm => _buildTextMessage(
        context,
        colorScheme,
        vm,
      ),
      final GenUiViewModel vm => _buildGenUiMessage(context, vm),
      final ErrorMessageViewModel vm => _buildErrorMessage(context, vm),
      final LoadingMessageViewModel vm => _buildLoadingMessage(
        context,
        colorScheme,
        vm,
      ),
      final ToolCallViewModel vm => _buildToolCallMessage(context, vm),
      final ToolCallGroupViewModel vm => _buildToolCallGroupMessage(
        context,
        vm,
      ),
      _ => _buildDefaultMessage(
        context,
        colorScheme,
        viewModel,
      ), // Handle unhandled types
    };
  }

  /// Build text message with optional thinking and tool calls.
  Widget _buildTextMessage(
    BuildContext context,
    ColorScheme colorScheme,
    TextMessageViewModel vm,
  ) {
    final bubbleColor = _isUser
        ? colorScheme.primaryContainer
        : colorScheme.surfaceContainerHighest;
    final textColor = _isUser
        ? colorScheme.onPrimaryContainer
        : colorScheme.onSurface;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: bubbleColor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Thinking section (for agent messages)
          if (_isAgent &&
              vm.thinkingText != null &&
              vm.thinkingText!.isNotEmpty)
            CollapsibleThinkingWidget(
              thinkingText: vm.thinkingText!,
              isStreaming: vm.isThinkingStreaming,
              isExpanded: vm.isThinkingExpanded || vm.isThinkingStreaming,
              onToggle: onToggleThinking ?? () {},
            ),

          // Main text content
          StreamingMarkdownWidget(
            text: vm.text,
            messageId: vm.id,
            isStreaming: vm.isStreaming,
            textStyle: TextStyle(color: textColor),
            onQuote: onQuote,
          ),

          // Citations section (for agent messages with citations)
          if (_isAgent && vm.citations.isNotEmpty)
            CollapsibleCitationsWidget(
              citations: vm.citations,
              isExpanded: vm.isCitationsExpanded,
              onToggle: onToggleCitations ?? () {},
              roomId: roomId,
            ),

          // Feedback chips and copy button (for finalized agent messages)
          if (_isAgent && !vm.isStreaming)
            _MessageActionsRow(messageId: vm.id, messageText: vm.text),
        ],
      ),
    );
  }

  /// Build GenUI widget message.
  Widget _buildGenUiMessage(BuildContext context, GenUiViewModel vm) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        GenUiMessageWidget(content: vm.content, onEvent: onGenUiEvent),
        // Add feedback for agent GenUI messages
        if (_isAgent)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: _MessageActionsRow(
              messageId: vm.id,
              messageText: '[Widget: ${vm.content.widgetName}]',
              genUiContent: vm.content,
            ),
          ),
      ],
    );
  }

  /// Build error message.
  Widget _buildErrorMessage(BuildContext context, ErrorMessageViewModel vm) {
    return FriendlyErrorCard(
      errorInfo:
          vm.errorInfo ??
          ChatErrorInfo.server(message: vm.message, details: vm.message),
      fallbackMessage: vm.message,
    );
  }

  /// Build loading indicator.
  Widget _buildLoadingMessage(
    BuildContext context,
    ColorScheme colorScheme,
    LoadingMessageViewModel vm,
  ) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(width: 12),
          Text(
            'Agent is thinking...',
            style: TextStyle(
              color: colorScheme.onSurfaceVariant,
              fontStyle: FontStyle.italic,
            ),
          ),
        ],
      ),
    );
  }

  /// Build compact tool call indicator.
  Widget _buildToolCallMessage(BuildContext context, ToolCallViewModel vm) {
    return CompactToolCallIndicator(
      toolName: vm.toolCallName,
      status: vm.status,
    );
  }

  /// Build grouped tool call summary.
  Widget _buildToolCallGroupMessage(
    BuildContext context,
    ToolCallGroupViewModel vm,
  ) {
    return ToolCallSummaryWidget(
      toolCalls: vm.toolCalls,
      isExpanded: vm.isExpanded,
      onToggle: onToggleToolGroup ?? () {},
    );
  }

  /// Default message builder for unhandled ViewModel types.
  Widget _buildDefaultMessage(
    BuildContext context,
    ColorScheme colorScheme,
    ChatMessageViewModel vm,
  ) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        'Unhandled message type: ${vm.runtimeType}',
        style: TextStyle(color: colorScheme.onErrorContainer),
      ),
    );
  }
}

/// Row with feedback chips and copy button for messages.
class _MessageActionsRow extends ConsumerStatefulWidget {
  const _MessageActionsRow({
    required this.messageId,
    required this.messageText,
    this.genUiContent,
  });
  final String messageId;
  final String messageText;
  final GenUiContent? genUiContent;

  @override
  ConsumerState<_MessageActionsRow> createState() => _MessageActionsRowState();
}

class _MessageActionsRowState extends ConsumerState<_MessageActionsRow> {
  bool _copied = false;
  bool _sentToCanvas = false;

  Future<void> _copyToClipboard() async {
    await Clipboard.setData(ClipboardData(text: widget.messageText));
    setState(() => _copied = true);
    Future<void>.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _copied = false);
    });
  }

  void _sendToCanvas() {
    final useCase = ref.read(sendToCanvasUseCaseProvider);
    final result = useCase.execute(
      content: widget.messageText,
      sourceMessageId: widget.messageId,
      genUiContent: widget.genUiContent,
    );

    if (result is SendToCanvasSuccess) {
      setState(() => _sentToCanvas = true);
      Future<void>.delayed(const Duration(seconds: 2), () {
        if (mounted) setState(() => _sentToCanvas = false);
      });
    }
  }

  void _handleFeedback(FeedbackRating rating) {
    final useCase = ref.read(sendFeedbackUseCaseProvider);
    useCase.handleFeedbackTap(
      context: context,
      messageId: widget.messageId,
      rating: rating,
    );
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final feedbackState = ref.watch(feedbackProvider);
    final existingFeedback = feedbackState.feedback[widget.messageId];
    final feedbackModel = FeedbackChipModel(
      currentRating: existingFeedback?.rating,
      comment: existingFeedback?.comment,
    );

    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          FeedbackChip(
            model: feedbackModel,
            onThumbsUp: () => _handleFeedback(FeedbackRating.positive),
            onThumbsDown: () => _handleFeedback(FeedbackRating.negative),
          ),
          const Spacer(),
          // Send to canvas button
          Tooltip(
            message: _sentToCanvas ? 'Sent!' : 'Send to canvas',
            child: InkWell(
              onTap: _sendToCanvas,
              borderRadius: BorderRadius.circular(16),
              child: Padding(
                padding: const EdgeInsets.all(6),
                child: Icon(
                  _sentToCanvas
                      ? Icons.check
                      : Icons.dashboard_customize_outlined,
                  size: 16,
                  color: _sentToCanvas ? Colors.green : colorScheme.outline,
                ),
              ),
            ),
          ),
          const SizedBox(width: 4),
          // Copy button
          Tooltip(
            message: _copied ? 'Copied!' : 'Copy message',
            child: InkWell(
              onTap: _copyToClipboard,
              borderRadius: BorderRadius.circular(16),
              child: Padding(
                padding: const EdgeInsets.all(6),
                child: Icon(
                  _copied ? Icons.check : Icons.copy_outlined,
                  size: 16,
                  color: _copied ? Colors.green : colorScheme.outline,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
