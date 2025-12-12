import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/models/chat_models.dart';
import '../../core/network/room_session.dart';
import '../../core/providers/panel_providers.dart';
import '../../core/services/agui_service.dart';
import '../../core/services/chat_search_service.dart';
import '../../core/services/local_tools_service.dart';
import '../../core/services/rooms_service.dart';
import '../../core/utils/debug_log.dart';
import '../room/welcome_card.dart';
import 'widgets/chat_input_area.dart';
import 'widgets/chat_message_list.dart';
import 'widgets/chat_search_bar.dart';

/// Chat content widget that can be embedded in various layouts.
///
/// Contains the custom chat message list and handles message sending/receiving.
/// Subscribes to RoomSession's message stream for updates.
class ChatContent extends ConsumerStatefulWidget {
  const ChatContent({super.key});

  @override
  ConsumerState<ChatContent> createState() => _ChatContentState();
}

class _ChatContentState extends ConsumerState<ChatContent> {
  final TextEditingController _inputController = TextEditingController();
  final FocusNode _inputFocusNode = FocusNode();
  final ScrollController _scrollController = ScrollController();
  String? _previousRoomId;

  // Track active search widgets and their callbacks
  final Map<String, void Function(String, Map<String, dynamic>)> _searchCallbacks = {};

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

  /// Core send logic - simplified to use ConnectionManager directly.
  Future<void> _handleSendText(String text) async {
    if (text.isEmpty) return;

    _inputController.clear();

    final connectionManager = ref.read(connectionManagerProvider);
    final localToolsService = ref.read(localToolsServiceProvider);
    final roomId = ref.read(selectedRoomProvider);

    if (roomId == null) {
      DebugLog.error('No room selected');
      return;
    }

    // Check for slash commands (handled locally, not sent to backend)
    if (text.startsWith('/')) {
      final session = connectionManager.getSession(roomId);
      final handled = _handleSlashCommand(text, session);
      if (handled) return;
    }

    // Check if ConnectionManager is configured
    if (!connectionManager.isConfigured) {
      final session = connectionManager.getSession(roomId);
      session.addErrorMessage(
        'Server not configured',
        errorCode: 'NOT_CONFIGURED',
      );
      return;
    }

    // Get current canvas state to send with request
    final canvasState = ref.read(canvasProvider);

    try {
      await connectionManager.chat(
        roomId: roomId,
        userMessage: text,
        localToolsService: localToolsService,
        uiToolHandler: (toolCallId, toolName, args) async {
          if (!mounted) return {'skipped': true, 'reason': 'disposed'};
          return _handleUiTool(toolCallId, toolName, args, roomId);
        },
        onCanvasUpdate: (operation, widgetName, data) {
          if (!mounted) return;
          final canvasNotifier = ref.read(canvasProvider.notifier);
          switch (operation) {
            case 'clear':
              canvasNotifier.clear();
            case 'replace':
              canvasNotifier.replaceAll(widgetName, data);
            default:
              canvasNotifier.addItem(widgetName, data);
          }
        },
        onContextUpdate: (eventType, {String? summary, Map<String, dynamic>? data}) {
          if (!mounted) return;
          final contextNotifier = ref.read(contextPaneProvider.notifier);
          switch (eventType) {
            case 'userMessage':
              contextNotifier.addTextMessage(summary ?? '', isUser: true);
            case 'textMessage':
              contextNotifier.addTextMessage(summary ?? '', isUser: false);
            case 'runStarted':
              contextNotifier.addAgUiEvent('Run Started', summary: summary);
            case 'runFinished':
              contextNotifier.addAgUiEvent('Run Finished');
            case 'toolCall':
              contextNotifier.addToolCall(summary ?? 'tool', summary: 'started');
            case 'toolResult':
              contextNotifier.addAgUiEvent('Tool Result');
            case 'genUiRender':
              contextNotifier.addGenUiRender(summary ?? 'Widget');
            case 'stateSnapshot':
              if (data != null) contextNotifier.updateState(data);
            case 'stateDelta':
              if (data != null) contextNotifier.applyDelta(data);
            case 'thinking':
              contextNotifier.addAgUiEvent('Thinking');
            case 'error':
              contextNotifier.addAgUiEvent('Error', summary: summary);
            case 'localToolExecution':
              final parts = summary?.split(': ') ?? [];
              if (parts.length >= 2) {
                contextNotifier.addLocalToolExecution(parts[0], status: parts[1]);
              }
          }
        },
        onActivityUpdate: (isActive, {String? eventType, String? toolName}) {
          if (!mounted) return;
          final activityNotifier = ref.read(activityStatusProvider.notifier);
          if (isActive) {
            if (eventType != null) {
              activityNotifier.handleEvent(eventType, toolName: toolName);
            } else {
              activityNotifier.startActivity();
            }
          } else {
            activityNotifier.stopActivity();
          }
        },
        state: canvasState.toJson(),
      );
    } catch (e) {
      DebugLog.error('Error sending message: $e');
      if (mounted) {
        final session = connectionManager.getSession(roomId);
        final errorStr = e.toString().toLowerCase();
        if (errorStr.contains('socket') ||
            errorStr.contains('connection') ||
            errorStr.contains('timeout') ||
            errorStr.contains('network')) {
          session.addErrorMessage(e.toString());
        } else {
          session.addErrorMessage(e.toString());
        }
      }
    }
  }

  /// Handle UI tools (canvas_render, genui_render) that need Riverpod access.
  Map<String, dynamic> _handleUiTool(
    String toolCallId,
    String toolName,
    Map<String, dynamic> args,
    String roomId,
  ) {
    final connectionManager = ref.read(connectionManagerProvider);
    final session = connectionManager.getSession(roomId);
    final canvasNotifier = ref.read(canvasProvider.notifier);
    final contextNotifier = ref.read(contextPaneProvider.notifier);

    if (toolName == 'genui_render') {
      final widgetName = args['widget_name'] as String? ?? 'Widget';
      final data = args['data'] as Map<String, dynamic>? ?? {};

      session.addGenUiMessage(
        GenUiContent(
          toolCallId: toolCallId,
          widgetName: widgetName,
          data: data,
        ),
      );
      contextNotifier.addGenUiRender(widgetName);
      return {'rendered': true, 'widget': widgetName};
    } else if (toolName == 'canvas_render') {
      final widgetName = args['widget_name'] as String? ?? 'Widget';
      final data = args['data'] as Map<String, dynamic>? ?? {};
      final position = args['position'] as String? ?? 'append';

      switch (position) {
        case 'clear':
          canvasNotifier.clear();
        case 'replace':
          canvasNotifier.replaceAll(widgetName, data);
        default:
          canvasNotifier.addItem(widgetName, data);
      }
      contextNotifier.addCanvasRender(widgetName, position);
      return {'rendered': true, 'widget': widgetName, 'position': position};
    }

    return {'error': 'Unknown UI tool: $toolName'};
  }

  // ===========================================================================
  // SLASH COMMANDS (local handling)
  // ===========================================================================

  /// Stubbed staff data for /search staff command
  static const List<Map<String, dynamic>> _stubbedStaffData = [
    {'id': 'u1', 'title': 'John Smith', 'subtitle': 'Engineering Lead'},
    {'id': 'u2', 'title': 'Jane Doe', 'subtitle': 'Product Manager'},
    {'id': 'u3', 'title': 'Bob Wilson', 'subtitle': 'Senior Developer'},
    {'id': 'u4', 'title': 'Alice Johnson', 'subtitle': 'UX Designer'},
    {'id': 'u5', 'title': 'Charlie Brown', 'subtitle': 'DevOps Engineer'},
    {'id': 'u6', 'title': 'Diana Prince', 'subtitle': 'QA Lead'},
    {'id': 'u7', 'title': 'Edward Norton', 'subtitle': 'Backend Developer'},
    {'id': 'u8', 'title': 'Fiona Apple', 'subtitle': 'Frontend Developer'},
    {'id': 'u9', 'title': 'George Lucas', 'subtitle': 'Data Scientist'},
    {'id': 'u10', 'title': 'Hannah Montana', 'subtitle': 'Marketing Manager'},
  ];

  /// Stubbed projects data for /list projects command
  static const List<Map<String, dynamic>> _stubbedProjectsData = [
    {
      'id': 'p1',
      'title': 'Mobile App Redesign',
      'description': 'Complete overhaul of the customer-facing mobile application',
      'required_skills': ['Flutter', 'Dart', 'Figma', 'UX Research'],
      'status': 'open',
    },
    {
      'id': 'p2',
      'title': 'Data Pipeline Migration',
      'description': 'Migrate legacy ETL pipelines to cloud-native architecture',
      'required_skills': ['Python', 'AWS', 'Kubernetes', 'Docker'],
      'status': 'open',
    },
    {
      'id': 'p3',
      'title': 'ML Recommendation Engine',
      'description': 'Build personalized recommendation system for e-commerce',
      'required_skills': ['Python', 'Machine Learning', 'TensorFlow', 'PostgreSQL'],
      'status': 'open',
    },
  ];

  /// Demo definitions with walkthrough steps
  static const Map<String, Map<String, dynamic>> _demos = {
    'team-builder': {
      'title': 'Team Builder',
      'description': 'Build an optimal team for a project based on required skills',
      'steps': [
        '1. Type: /list projects',
        '2. Pick a project (e.g., "Mobile App Redesign")',
        '3. Say: "Build me a team for the Mobile App Redesign project"',
      ],
    },
  };

  /// Handle slash commands locally.
  bool _handleSlashCommand(String text, RoomSession session) {
    final parts = text.split(' ');
    final command = parts[0].toLowerCase();
    final args = parts.skip(1).toList();

    switch (command) {
      case '/search':
        final searchType = args.isNotEmpty ? args[0] : 'items';
        _showSearchWidget(searchType, session);
        return true;

      case '/list':
        final listType = args.isNotEmpty ? args[0] : 'items';
        _showListWidget(listType, session);
        return true;

      case '/demo':
        final demoName = args.isNotEmpty ? args.join('-') : '';
        _showDemo(demoName, session);
        return true;

      case '/canvas':
        _showCanvasState(session);
        return true;

      case '/help':
        session.addSystemMessage(
          'Available commands:\n'
          '• /search staff - Search and select staff members\n'
          '• /list projects - Show available projects\n'
          '• /list demos - Show available demos\n'
          '• /demo <name> - Walk through a specific demo\n'
          '• /canvas - Show current canvas contents\n'
          '• /help - Show this help message',
        );
        return true;

      default:
        return false;
    }
  }

  void _showSearchWidget(String searchType, RoomSession session) {
    session.addUserMessage('/search $searchType');

    List<Map<String, dynamic>> items;
    String placeholder;

    switch (searchType) {
      case 'staff':
        items = _stubbedStaffData;
        placeholder = 'Search staff by name or role...';
      default:
        items = _stubbedStaffData;
        placeholder = 'Search...';
    }

    final searchId = 'search-${DateTime.now().millisecondsSinceEpoch}';

    _searchCallbacks[searchId] = (eventName, payload) {
      _handleSearchWidgetEvent(eventName, payload, searchType, session);
      if (eventName == 'submit' || eventName == 'cancel') {
        _searchCallbacks.remove(searchId);
      }
    };

    session.addGenUiMessage(
      GenUiContent(
        toolCallId: searchId,
        widgetName: 'SearchWidget',
        data: {
          '_toolCallId': searchId,
          'placeholder': placeholder,
          'multi_select': true,
          'items': items,
          'search_type': searchType,
        },
      ),
    );
  }

  void _showListWidget(String listType, RoomSession session) {
    session.addUserMessage('/list $listType');

    switch (listType) {
      case 'projects':
        for (final project in _stubbedProjectsData) {
          session.addGenUiMessage(
            GenUiContent(
              toolCallId: 'project-${project['id']}-${DateTime.now().millisecondsSinceEpoch}',
              widgetName: 'ProjectCard',
              data: project,
            ),
          );
        }
      case 'demos':
        final demoList = _demos.entries.map((e) {
          final demo = e.value;
          return '• /demo ${e.key} - ${demo['title']}\n  ${demo['description']}';
        }).join('\n\n');
        session.addSystemMessage('Available Demos:\n\n$demoList');
      default:
        session.addSystemMessage('Unknown list type: $listType\nTry: /list projects or /list demos');
    }
  }

  void _showCanvasState(RoomSession session) {
    session.addUserMessage('/canvas');
    final canvasState = ref.read(canvasProvider);
    session.addSystemMessage(canvasState.toSummary());
  }

  void _showDemo(String demoName, RoomSession session) {
    session.addUserMessage('/demo $demoName');

    if (demoName.isEmpty) {
      session.addSystemMessage('Usage: /demo <name>\nType /list demos to see available demos.');
      return;
    }

    final demo = _demos[demoName];
    if (demo == null) {
      final available = _demos.keys.join(', ');
      session.addSystemMessage('Unknown demo: $demoName\nAvailable: $available');
      return;
    }

    final steps = (demo['steps'] as List<dynamic>).join('\n');
    session.addSystemMessage(
      '${demo['title']}\n'
      '${'-' * (demo['title'] as String).length}\n'
      '${demo['description']}\n\n'
      'Walkthrough:\n$steps',
    );
  }

  void _handleSearchWidgetEvent(
    String eventName,
    Map<String, dynamic> payload,
    String searchType,
    RoomSession session,
  ) {
    switch (eventName) {
      case 'submit':
        final selected = payload['selected'] as List<dynamic>? ?? [];
        if (selected.isNotEmpty) {
          final names = selected.map((item) {
            final map = item as Map<String, dynamic>;
            return '${map['title']} (${map['subtitle']})';
          }).join(', ');

          final prefill = 'Selected $searchType: $names\n';
          _inputController.text = prefill;
          _inputController.selection = TextSelection.fromPosition(
            TextPosition(offset: prefill.length),
          );
        }

      case 'cancel':
        session.addSystemMessage('Search cancelled.');
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
    final toolCallId = arguments['_toolCallId'] as String?;
    if (toolCallId != null && _searchCallbacks.containsKey(toolCallId)) {
      final callback = _searchCallbacks[toolCallId];
      final payload = Map<String, dynamic>.from(arguments);
      payload.remove('_toolCallId');
      callback?.call(eventName, payload);
    }
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
    final selectedRoomId = ref.watch(selectedRoomProvider);
    final selectedRoom = ref.watch(selectedRoomDataProvider);
    final searchState = ref.watch(chatSearchProvider);
    final activityStatus = ref.watch(activityStatusProvider);

    // Get messages from ConnectionManager (the source of truth)
    final connectionManager = ref.watch(connectionManagerProvider);
    final messages = selectedRoomId != null
        ? connectionManager.getMessages(selectedRoomId)
        : <ChatMessage>[];
    final isAgentTyping = selectedRoomId != null
        ? connectionManager.isAgentTyping(selectedRoomId)
        : false;

    // Focus input when room changes
    _checkRoomChange(selectedRoomId);

    // Only count agent messages to prevent suggestion flash on user submit
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
                  // Search bar (when active)
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
                      isAgentTyping: isAgentTyping,
                      scrollController: _scrollController,
                      maxBubbleWidth: messageMaxWidth,
                      onQuote: _handleQuote,
                      onToggleThinking: (messageId) {
                        if (selectedRoomId != null) {
                          connectionManager.getSession(selectedRoomId)
                              .toggleThinkingExpanded(messageId);
                        }
                      },
                      onToggleToolGroup: (messageId) {
                        // Tool group toggle - handled by session if needed
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
                  // Activity status bar OR input area
                  if (activityStatus.isActive && activityStatus.currentMessage != null)
                    ActivityStatusBar(
                      message: activityStatus.currentMessage!,
                      onStop: () async {
                        if (selectedRoomId != null) {
                          DebugLog.network('Stop button: cancelling run for room $selectedRoomId');
                          await connectionManager.cancelRun(selectedRoomId);
                          ref.read(activityStatusProvider.notifier).stopActivity();
                        }
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
