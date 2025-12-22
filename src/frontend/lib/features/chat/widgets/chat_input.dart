import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_frontend/core/providers/active_run_provider.dart';

/// Widget for chat message input.
///
/// Provides:
/// - Text field for typing messages
/// - Send button (enabled/disabled based on canSendMessageProvider)
/// - Keyboard shortcuts: Enter to send, Shift+Enter for new line
/// - Auto-clear input after send
///
/// Example:
/// ```dart
/// ChatInput(
///   onSend: (text) {
///     // Handle sending message
///   },
/// )
/// ```
class ChatInput extends ConsumerStatefulWidget {
  /// Creates a chat input widget.
  const ChatInput({
    required this.onSend,
    super.key,
  });

  /// Callback invoked when user sends a message.
  final void Function(String text) onSend;

  @override
  ConsumerState<ChatInput> createState() => _ChatInputState();
}

class _ChatInputState extends ConsumerState<ChatInput> {
  late final TextEditingController _controller;
  late final FocusNode _focusNode;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();
    _focusNode = FocusNode();
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _handleSend() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;

    widget.onSend(text);
    _controller.clear();
  }

  @override
  Widget build(BuildContext context) {
    final canSend = ref.watch(canSendMessageProvider);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.1),
            blurRadius: 4,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: CallbackShortcuts(
              bindings: {
                const SingleActivator(LogicalKeyboardKey.enter):
                    canSend ? _handleSend : () {},
                const SingleActivator(
                  LogicalKeyboardKey.escape,
                ): () => _focusNode.unfocus(),
              },
              child: Semantics(
                label: 'Chat message input',
                child: TextField(
                  controller: _controller,
                  focusNode: _focusNode,
                  maxLines: null,
                  textInputAction: TextInputAction.newline,
                  decoration: InputDecoration(
                    hintText: canSend
                        ? 'Type a message...'
                        : 'Select a room to start chatting',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(24),
                    ),
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 12,
                    ),
                  ),
                  enabled: canSend,
                  onChanged: (_) => setState(() {}),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          IconButton(
            tooltip: 'Send message',
            onPressed: canSend && _controller.text.trim().isNotEmpty
                ? _handleSend
                : null,
            icon: const Icon(Icons.send),
            style: IconButton.styleFrom(
              backgroundColor: canSend && _controller.text.trim().isNotEmpty
                  ? Theme.of(context).colorScheme.primary
                  : null,
              foregroundColor: canSend && _controller.text.trim().isNotEmpty
                  ? Theme.of(context).colorScheme.onPrimary
                  : null,
            ),
          ),
        ],
      ),
    );
  }
}
