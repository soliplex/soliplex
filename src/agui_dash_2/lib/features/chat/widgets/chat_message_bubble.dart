import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/models/chat_models.dart';
import '../../../core/providers/panel_providers.dart';
import '../../../core/services/canvas_content_service.dart';
import 'chat_typing_indicator.dart';
import 'collapsible_thinking_widget.dart';
import 'friendly_error_card.dart';
import 'genui_message_widget.dart';
import 'message_feedback_chips.dart';
import 'streaming_markdown_widget.dart';
import 'tool_call_summary_widget.dart';

/// Message bubble that handles all message types directly.
///
/// Replaces DashChat's message rendering with direct ChatMessage → Widget routing.
/// No conversion layer needed.
class ChatMessageBubble extends ConsumerWidget {
  final ChatMessage message;
  final ChatMessage? previousMessage;
  final ChatMessage? nextMessage;
  final double maxWidth;
  final void Function(String quotedText)? onQuote;
  final VoidCallback? onToggleThinking;
  final VoidCallback? onToggleToolGroup;
  final void Function(String eventName, Map<String, Object?> arguments)? onGenUiEvent;

  const ChatMessageBubble({
    super.key,
    required this.message,
    this.previousMessage,
    this.nextMessage,
    this.maxWidth = double.infinity,
    this.onQuote,
    this.onToggleThinking,
    this.onToggleToolGroup,
    this.onGenUiEvent,
  });

  bool get _isUser => message.user.id == ChatUser.user.id;
  bool get _isAgent => message.user.id == ChatUser.agent.id;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    // Determine if we should show avatar (first message from this user in a group)
    final showAvatar = previousMessage?.user.id != message.user.id;

    return Row(
      mainAxisAlignment: _isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        // Agent avatar (left side)
        if (!_isUser && showAvatar)
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: ChatAvatar(user: message.user),
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
    // Route to appropriate builder based on message type
    return switch (message.type) {
      MessageType.text => _buildTextMessage(context, colorScheme),
      MessageType.genUi => _buildGenUiMessage(context),
      MessageType.error => _buildErrorMessage(context),
      MessageType.loading => _buildLoadingMessage(context, colorScheme),
      MessageType.toolCall => _buildToolCallMessage(context),
      MessageType.toolCallGroup => _buildToolCallGroupMessage(context),
    };
  }

  /// Build text message with optional thinking and tool calls.
  Widget _buildTextMessage(BuildContext context, ColorScheme colorScheme) {
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
              message.thinkingText != null &&
              message.thinkingText!.isNotEmpty)
            CollapsibleThinkingWidget(
              thinkingText: message.thinkingText!,
              isStreaming: message.isThinkingStreaming,
              isExpanded: message.isThinkingExpanded || message.isThinkingStreaming,
              onToggle: onToggleThinking ?? () {},
            ),

          // Main text content
          StreamingMarkdownWidget(
            text: message.text ?? '',
            messageId: message.id,
            isStreaming: message.isStreaming,
            textStyle: TextStyle(color: textColor),
            onQuote: onQuote,
          ),

          // Tool calls section (for agent messages)
          if (_isAgent &&
              message.toolCalls != null &&
              message.toolCalls!.isNotEmpty)
            ToolCallSummaryWidget(
              toolCalls: message.toolCalls!,
              isExpanded: message.isToolGroupExpanded,
              onToggle: onToggleToolGroup ?? () {},
            ),

          // Feedback chips and copy button (for finalized agent messages)
          if (_isAgent && !message.isStreaming)
            _MessageActionsRow(
              messageId: message.id,
              messageText: message.text ?? '',
            ),
        ],
      ),
    );
  }

  /// Build GenUI widget message.
  Widget _buildGenUiMessage(BuildContext context) {
    if (message.genUiContent == null) {
      return _buildErrorMessage(context);
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        GenUiMessageWidget(
          content: message.genUiContent!,
          onEvent: onGenUiEvent,
        ),
        // Add feedback for agent GenUI messages
        if (_isAgent)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: _MessageActionsRow(
              messageId: message.id,
              messageText: '[Widget: ${message.genUiContent!.widgetName}]',
              genUiContent: message.genUiContent,
            ),
          ),
      ],
    );
  }

  /// Build error message.
  Widget _buildErrorMessage(BuildContext context) {
    if (message.errorInfo != null) {
      return FriendlyErrorCard(
        errorInfo: message.errorInfo!,
        fallbackMessage: message.errorMessage,
      );
    }
    return FriendlyErrorCard.fromMessage(
      message.errorMessage ?? 'An error occurred',
    );
  }

  /// Build loading indicator.
  Widget _buildLoadingMessage(BuildContext context, ColorScheme colorScheme) {
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
  Widget _buildToolCallMessage(BuildContext context) {
    return CompactToolCallIndicator(
      toolName: message.toolCallName ?? 'Unknown tool',
      status: message.toolCallStatus ?? 'executing',
    );
  }

  /// Build grouped tool call summary.
  Widget _buildToolCallGroupMessage(BuildContext context) {
    if (message.toolCalls == null || message.toolCalls!.isEmpty) {
      return const SizedBox.shrink();
    }
    return ToolCallSummaryWidget(
      toolCalls: message.toolCalls!,
      isExpanded: message.isToolGroupExpanded,
      onToggle: onToggleToolGroup ?? () {},
    );
  }
}

/// Row with feedback chips and copy button for messages.
class _MessageActionsRow extends ConsumerStatefulWidget {
  final String messageId;
  final String messageText;
  final GenUiContent? genUiContent;

  const _MessageActionsRow({
    required this.messageId,
    required this.messageText,
    this.genUiContent,
  });

  @override
  ConsumerState<_MessageActionsRow> createState() => _MessageActionsRowState();
}

class _MessageActionsRowState extends ConsumerState<_MessageActionsRow> {
  bool _copied = false;
  bool _sentToCanvas = false;
  final _contentService = CanvasContentService();

  Future<void> _copyToClipboard() async {
    await Clipboard.setData(ClipboardData(text: widget.messageText));
    setState(() => _copied = true);
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _copied = false);
    });
  }

  void _sendToCanvas() {
    final canvasNotifier = ref.read(canvasProvider.notifier);

    // For GenUI widgets, send the actual widget directly
    if (widget.genUiContent != null) {
      final genUi = widget.genUiContent!;
      canvasNotifier.addItem(genUi.widgetName, genUi.data);
    } else {
      // For text messages, analyze and convert
      if (widget.messageText.isEmpty) return;

      final analysis = _contentService.analyze(
        widget.messageText,
        sourceMessageId: widget.messageId,
      );
      canvasNotifier.addItem(analysis.widgetName, analysis.data);
    }

    // Show feedback via icon change
    setState(() => _sentToCanvas = true);
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _sentToCanvas = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          MessageFeedbackChips(messageId: widget.messageId),
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
