import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/models/chat_models.dart';
import '../../core/network/connection_manager.dart';
import '../../core/network/server_room_key.dart';
import '../../core/providers/panel_providers.dart';
import '../../core/services/chat_search_service.dart';
import '../../core/services/local_tools_service.dart';
import '../../core/services/rooms_service.dart';
import '../../core/utils/debug_log.dart';
import '../room/welcome_card.dart';
import 'services/slash_command_service.dart';
import 'widgets/chat_input_area.dart';
import 'widgets/chat_message_list.dart';
import 'widgets/chat_search_bar.dart';

/// Chat content widget that can be embedded in various layouts.
///
/// Contains the custom chat message list and handles message sending/receiving.
class ChatContent extends ConsumerStatefulWidget {
  final String? roomId;

  const ChatContent({super.key, this.roomId});

  @override
  ConsumerState<ChatContent> createState() => _ChatContentState();
}

class _ChatContentState extends ConsumerState<ChatContent> {
  final TextEditingController _inputController = TextEditingController();
  final FocusNode _inputFocusNode = FocusNode();
  final ScrollController _scrollController = ScrollController();
  String? _previousRoomId;

  @override
  void dispose() {
    _inputController.dispose();
    _inputFocusNode.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  /// Focus the input field when room changes.
  void _checkRoomChange(String? currentRoomId) {
    if (currentRoomId != null && currentRoomId != _previousRoomId) {
      _previousRoomId = currentRoomId;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _inputFocusNode.requestFocus();
        }
      });
    }
  }

  /// Send a message.
  void _sendMessage() {
    final text = _inputController.text.trim();
    if (text.isEmpty) return;
    _handleSendText(text);
  }

  /// Core send logic - routed via ConnectionManager.
  Future<void> _handleSendText(String text) async {
    if (text.isEmpty) return;

    final roomId = widget.roomId;
    if (roomId == null) return;

    _inputController.clear();

    final connectionManager = ref.read(connectionManagerProvider);
    final localToolsService = ref.read(localToolsServiceProvider);
    final slashCommandService = ref.read(slashCommandServiceProvider);

    final session = connectionManager.getSession(roomId);

    // Check for slash commands (handled locally)
    if (text.startsWith('/')) {
      final handled = slashCommandService.handleCommand(text, session);
      if (handled) return;
    }

    // Check if ConnectionManager is configured
    if (!connectionManager.isConfigured) {
      session.addErrorMessage('Server not configured');
      return;
    }

    // Get current canvas state (scoped to room)
    final serverId = connectionManager.activeServerId;
    final key = ServerRoomKey(serverId: serverId!, roomId: roomId);
    final canvasState = ref.read(roomCanvasProvider(key));

    try {
      await connectionManager.chat(
        roomId: roomId,
        userMessage: text,
        localToolsService: localToolsService,
        state: canvasState.toJson(),
      );
    } catch (e) {
      DebugLog.error('Error sending message: $e');
      if (mounted) {
        session.addErrorMessage(e.toString());
      }
    }
  }

  // ===========================================================================
  // UI HELPERS
  // ===========================================================================

  Future<void> _pasteFromClipboard() async {
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    if (data?.text != null) {
      final text = _inputController.text;
      final selection = _inputController.selection;
      final newText = text.replaceRange(
        selection.start,
        selection.end,
        data!.text!,
      );
      _inputController.text = newText;
      _inputController.selection = TextSelection.collapsed(
        offset: selection.start + data.text!.length,
      );
    }
  }

  void _handleGenUiEvent(String eventName, Map<String, Object?> arguments) {
    final slashCommandService = ref.read(slashCommandServiceProvider);
    slashCommandService.handleGenUiEvent(eventName, arguments, (text) {
      _inputController.text = text;
      _inputController.selection = TextSelection.fromPosition(
        TextPosition(offset: text.length),
      );
    });
  }

  void _handleQuote(String quotedText) {
    final currentText = _inputController.text;
    final newText = currentText.isEmpty
        ? '$quotedText\n\n'
        : '$currentText\n\n$quotedText\n\n';
    _inputController.text = newText;
    _inputController.selection = TextSelection.collapsed(
      offset: newText.length,
    );
  }

  // ===========================================================================
  // BUILD
  // ===========================================================================

  @override
  Widget build(BuildContext context) {
    final roomId = widget.roomId;
    
    if (roomId == null) {
      return const Center(
        child: Text(
          'Select a room to start chatting',
          style: TextStyle(color: Colors.grey),
        ),
      );
    }

    final connectionManager = ref.watch(connectionManagerProvider);
    final serverId = connectionManager.activeServerId;

    if (serverId == null) {
      return const Center(child: CircularProgressIndicator());
    }

    final key = ServerRoomKey(serverId: serverId, roomId: roomId);
    
    // Get room data
    final roomsState = ref.watch(roomsProvider);
    final selectedRoom = roomsState.rooms.where((r) => r.id == roomId).firstOrNull;

    final searchState = ref.watch(chatSearchProvider);
    
    // Use scoped providers
    final activityStatus = ref.watch(roomActivityStatusProvider(key));
    final messagesAsync = ref.watch(roomMessageStreamProvider(key));
    final messages = messagesAsync.value ?? <ChatMessage>[];

    // Focus input when room changes
    _checkRoomChange(roomId);

    final hasAgentMessages = messages.any(
      (m) => m.user.id == ChatUser.agent.id,
    );

    return Shortcuts(
      shortcuts: {
        const SingleActivator(LogicalKeyboardKey.keyK, alt: true):
            const _PasteIntent(),
      },
      child: Actions(
        actions: {
          _PasteIntent: CallbackAction<_PasteIntent>(
            onInvoke: (_) {
              _pasteFromClipboard();
              return null;
            },
          ),
        },
        child: Focus(
          autofocus: true,
          child: LayoutBuilder(
            builder: (context, constraints) {
              final messageMaxWidth = constraints.maxWidth * 0.7;

              return Column(
                children: [
                  // Search bar
                  if (searchState.isActive)
                    ChatSearchBar(
                      messageIds: messages.map((m) => m.id).toList(),
                      getMessageText: (id) {
                        try {
                          final msg = messages.firstWhere((m) => m.id == id);
                          return msg.text ?? '';
                        } catch (_) {
                          return '';
                        }
                      },
                    ),
                  // Chat messages area
                  Expanded(
                    child: ChatMessageList(
                      messages: messages,
                      scrollController: _scrollController,
                      maxBubbleWidth: messageMaxWidth,
                      onQuote: _handleQuote,
                      onToggleThinking: (messageId) {
                        connectionManager
                            .getSession(roomId)
                            .toggleThinkingExpanded(messageId);
                      },
                      onToggleToolGroup: (messageId) {
                        // Tool group toggle
                      },
                      onGenUiEvent: _handleGenUiEvent,
                      welcomeWidget: !hasAgentMessages && selectedRoom != null
                          ? WelcomeCard(
                              room: selectedRoom,
                              onSuggestionTap: (suggestion) {
                                _inputController.text = suggestion;
                                _sendMessage();
                              },
                            )
                          : null,
                    ),
                  ),
                  // Activity status OR input
                  if (activityStatus.isActive)
                    ActivityStatusBar(
                      message: activityStatus.currentMessage ?? 'Generating...',
                      onStop: () async {
                        // The UI should automatically stop once the backend
                        // confirms the run is cancelled and sends a RunCancelledEvent.
                        // For immediate feedback, we also stop activity locally.
                        // No need for `ref.read(roomActivityStatusProvider(key).notifier).stopActivity();`
                        // as ConnectionManager event will trigger it.
                        await connectionManager.cancelRun(roomId);
                      },
                    )
                  else
                    ChatInputArea(
                      controller: _inputController,
                      focusNode: _inputFocusNode,
                      onSend: _sendMessage,
                      room: selectedRoom,
                      hasMessages: hasAgentMessages,
                      isLoading: activityStatus.isActive,
                      showWelcome: false,
                    ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}

/// Intent for paste action.
class _PasteIntent extends Intent {
  const _PasteIntent();
}