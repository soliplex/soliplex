import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../providers/providers.dart';
import 'message_bubble.dart';

/// Chat widget for displaying and sending messages.
///
/// Scoped to the current thread, showing all messages across runs.
class ChatWidget extends ConsumerStatefulWidget {
  const ChatWidget({super.key});

  @override
  ConsumerState<ChatWidget> createState() => _ChatWidgetState();
}

class _ChatWidgetState extends ConsumerState<ChatWidget> {
  final _messageController = TextEditingController();
  final _scrollController = ScrollController();
  bool _isAtBottom = true;

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom({bool animate = true}) {
    if (!_scrollController.hasClients) return;
    if (animate) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
    } else {
      _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
    }
  }

  Future<void> _sendMessage() async {
    final message = _messageController.text.trim();
    if (message.isEmpty) return;

    _messageController.clear();

    try {
      final sendMessage = ref.read(sendMessageProvider);
      await sendMessage(message);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final roomId = ref.watch(currentRoomProvider);
    final isActive = ref.watch(isAgentActiveProvider);

    if (roomId == null) {
      return const _EmptyChat(message: 'Select a room to start chatting');
    }

    final messagesAsync = ref.watch(roomMessagesProvider(roomId));

    return Column(
      children: [
        // Messages list
        Expanded(
          child: messagesAsync.when(
            data: (messages) {
              // Auto-scroll when new messages arrive and we're at bottom
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (_isAtBottom) {
                  _scrollToBottom(animate: false);
                }
              });

              if (messages.isEmpty) {
                return const _EmptyChat(message: 'Send a message to begin');
              }

              return NotificationListener<ScrollNotification>(
                onNotification: (notification) {
                  if (notification is ScrollUpdateNotification) {
                    final atBottom = _scrollController.position.pixels >=
                        _scrollController.position.maxScrollExtent - 50;
                    if (atBottom != _isAtBottom) {
                      setState(() {
                        _isAtBottom = atBottom;
                      });
                    }
                  }
                  return false;
                },
                child: ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(16),
                  itemCount: messages.length,
                  itemBuilder: (context, index) {
                    final message = messages[index];
                    return MessageBubble(
                      message: message,
                      key: ValueKey(message.id),
                    );
                  },
                ),
              );
            },
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => _EmptyChat(
              message: 'Error: $error',
              isError: true,
            ),
          ),
        ),

        // Scroll to bottom button
        if (!_isAtBottom)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Center(
              child: FloatingActionButton.small(
                onPressed: () => _scrollToBottom(),
                child: const Icon(Icons.arrow_downward),
              ),
            ),
          ),

        // Input area
        _ChatInput(
          controller: _messageController,
          isActive: isActive,
          onSend: _sendMessage,
          onCancel: () => ref.read(cancelRunProvider)(),
        ),
      ],
    );
  }
}

class _ChatInput extends StatelessWidget {
  const _ChatInput({
    required this.controller,
    required this.isActive,
    required this.onSend,
    required this.onCancel,
  });

  final TextEditingController controller;
  final bool isActive;
  final VoidCallback onSend;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border(
          top: BorderSide(
            color: Theme.of(context).dividerColor,
          ),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: TextField(
              controller: controller,
              decoration: InputDecoration(
                hintText: isActive ? 'Waiting for response...' : 'Type a message...',
                border: const OutlineInputBorder(),
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 10,
                ),
              ),
              maxLines: 4,
              minLines: 1,
              enabled: !isActive,
              onSubmitted: (_) => onSend(),
              textInputAction: TextInputAction.send,
            ),
          ),
          const SizedBox(width: 8),
          if (isActive)
            FloatingActionButton(
              onPressed: onCancel,
              mini: true,
              backgroundColor: Colors.red,
              foregroundColor: Colors.white,
              tooltip: 'Cancel',
              child: const Icon(Icons.stop),
            )
          else
            FloatingActionButton(
              onPressed: onSend,
              mini: true,
              tooltip: 'Send',
              child: const Icon(Icons.send),
            ),
        ],
      ),
    );
  }
}

class _EmptyChat extends StatelessWidget {
  const _EmptyChat({
    required this.message,
    this.isError = false,
  });

  final String message;
  final bool isError;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            isError ? Icons.error_outline : Icons.chat_bubble_outline,
            size: 64,
            color: isError ? Colors.red : Theme.of(context).colorScheme.outline,
          ),
          const SizedBox(height: 16),
          Text(
            message,
            style: TextStyle(
              fontSize: 16,
              color: isError ? Colors.red : Theme.of(context).colorScheme.outline,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
