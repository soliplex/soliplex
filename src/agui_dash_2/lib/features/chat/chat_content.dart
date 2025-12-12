import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:dash_chat_2/dash_chat_2.dart' as dash;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/models/chat_models.dart';
import '../../core/network/connection_manager.dart';
import '../../core/services/activity_status_service.dart';
import '../../core/services/agui_service.dart';
import '../../core/services/chat_search_service.dart';
import '../../core/services/canvas_service.dart';
import '../../core/services/chat_service.dart';
import '../../core/services/context_pane_service.dart';
import '../../core/services/local_tools_service.dart';
import '../../core/services/room_chat_service.dart';
import '../../core/services/rooms_service.dart';
import '../../core/utils/debug_log.dart';
import '../../infrastructure/quick_agui/tool_call_state.dart';
import 'builders/message_builder.dart';
import 'widgets/chat_input_area.dart';
import 'widgets/chat_search_bar.dart';
import 'widgets/collapsible_thinking_widget.dart';
import 'widgets/message_feedback_chips.dart';
import 'widgets/streaming_markdown_widget.dart';
import 'widgets/tool_call_summary_widget.dart';

/// Chat content widget that can be embedded in various layouts.
///
/// Contains the DashChat widget and handles message sending/receiving.
/// Can be used standalone or within layout containers.
class ChatContent extends ConsumerStatefulWidget {
  const ChatContent({super.key});

  @override
  ConsumerState<ChatContent> createState() => _ChatContentState();
}

class _ChatContentState extends ConsumerState<ChatContent> {
  late final MessageBuilder _messageBuilder;
  final TextEditingController _inputController = TextEditingController();
  final FocusNode _inputFocusNode = FocusNode();
  String? _previousRoomId;

  @override
  void initState() {
    super.initState();
    _messageBuilder = MessageBuilder(
      onGenUiEvent: _handleGenUiEvent,
      onToggleToolGroup: (messageId) {
        ref.read(chatProvider.notifier).toggleToolGroupExpanded(messageId);
      },
    );
  }

  @override
  void dispose() {
    _inputController.dispose();
    _inputFocusNode.dispose();
    super.dispose();
  }

  /// Focus the input field when room changes.
  void _checkRoomChange(String? currentRoomId) {
    if (currentRoomId != null && currentRoomId != _previousRoomId) {
      _previousRoomId = currentRoomId;
      // Schedule focus request after build
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _inputFocusNode.requestFocus();
        }
      });
    }
  }

  void _handleGenUiEvent(String eventName, Map<String, Object?> arguments) {
    // Check if this event has a toolCallId that matches a registered callback
    final toolCallId = arguments['_toolCallId'] as String?;
    if (toolCallId != null && _searchCallbacks.containsKey(toolCallId)) {
      final callback = _searchCallbacks[toolCallId];
      final payload = Map<String, dynamic>.from(arguments);
      payload.remove('_toolCallId');
      callback?.call(eventName, payload);
      return;
    }
    // Unhandled GenUI events are not shown to user
  }

  /// Send a message (called from ChatInputArea).
  void _sendMessage() {
    final text = _inputController.text.trim();
    if (text.isEmpty) return;
    _handleSendText(text);
  }

  /// Handle sending a message from DashChat's onSend callback.
  Future<void> _handleSend(dash.ChatMessage dashMessage) async {
    final text = dashMessage.text.trim();
    if (text.isEmpty) return;
    await _handleSendText(text);
  }

  /// Core send logic shared by both send methods.
  Future<void> _handleSendText(String text) async {
    if (text.isEmpty) return;

    // Clear input immediately after capturing text
    _inputController.clear();

    final chatNotifier = ref.read(chatProvider.notifier);
    final agUiService = ref.read(configuredAgUiServiceProvider);
    final localToolsService = ref.read(localToolsServiceProvider);
    final contextNotifier = ref.read(contextPaneProvider.notifier);
    final canvasNotifier = ref.read(canvasProvider.notifier);

    // Check for slash commands (handled locally, not sent to backend)
    if (text.startsWith('/')) {
      final handled = _handleSlashCommand(text, chatNotifier, canvasNotifier);
      if (handled) return;
    }

    // Add user message
    chatNotifier.addUserMessage(text);
    contextNotifier.addTextMessage(text, isUser: true);

    // Check if AG-UI is configured
    if (!agUiService.isConfigured) {
      chatNotifier.addServerError(
        'AG-UI server not configured',
        errorCode: 'NOT_CONFIGURED',
      );
      return;
    }

    // Get current canvas state to send with request
    final canvasState = ref.read(canvasProvider);

    try {
      // Use the chat() method which handles tool loop internally
      await agUiService.chat(
        text,
        localToolsService: localToolsService,
        state: canvasState.toJson(),
        onEvent: (event) {
          if (!mounted) return;
          _processEvent(event, chatNotifier, contextNotifier, canvasNotifier);
        },
        uiToolHandler: (toolCallId, toolName, args) async {
          // Prevent duplicate execution of the same tool call
          if (_processedUiToolCalls.contains(toolCallId)) {
            return {'skipped': true, 'reason': 'duplicate'};
          }
          _processedUiToolCalls.add(toolCallId);

          return _handleUiTool(
            toolName,
            args,
            chatNotifier,
            canvasNotifier,
            contextNotifier,
          );
        },
        onLocalToolExecution: (toolCallId, toolName, status) {
          // Deduplicate by tool call ID - skip if we've already processed this execution
          final trackingKey = '$toolCallId:$status';
          if (_processedToolNotifications.contains(trackingKey)) {
            return;
          }
          _processedToolNotifications.add(trackingKey);

          contextNotifier.addLocalToolExecution(toolName, status: status);

          // Add or update tool call message in chat
          if (status == 'executing') {
            final messageId = chatNotifier.addToolCallMessage(toolName);
            _toolCallMessageIds[toolCallId] = messageId;
          } else {
            final messageId = _toolCallMessageIds[toolCallId];
            if (messageId != null) {
              chatNotifier.updateToolCallStatus(messageId, status);
              if (status == 'completed' || status.startsWith('error')) {
                _toolCallMessageIds.remove(toolCallId);
              }
            }
          }
        },
        onToolStateChange: (change) {
          if (!mounted) return;
          _handleToolStateChange(change, contextNotifier);
        },
      );
      // Sync chat state to per-room provider after successful completion
      _syncToRoomProvider();
    } catch (e) {
      DebugLog.error('Error sending message: $e');
      if (mounted) {
        final errorStr = e.toString().toLowerCase();
        // Classify error based on exception content
        if (errorStr.contains('socket') ||
            errorStr.contains('connection') ||
            errorStr.contains('timeout') ||
            errorStr.contains('network')) {
          chatNotifier.addNetworkError(e.toString());
        } else {
          chatNotifier.addServerError(e.toString());
        }
        // Sync even on error so state is preserved
        _syncToRoomProvider();
      }
    }
  }

  /// Sync current chat state to the per-room provider for session preservation.
  void _syncToRoomProvider() {
    final agUiService = ref.read(configuredAgUiServiceProvider);
    final roomId = agUiService.currentRoomId;
    if (roomId == null) return;

    final messages = ref.read(chatProvider).messages;
    if (messages.isNotEmpty) {
      ref.read(roomChatProvider(roomId).notifier).loadMessages(messages);
      DebugLog.network('Synced ${messages.length} messages to room $roomId');
    }
  }

  /// Handle tool call state changes for context pane logging.
  ///
  /// Note: Tool call messages are added/updated via onLocalToolExecution callback.
  /// This handler only updates the ContextPaneNotifier for debugging/visibility.
  void _handleToolStateChange(
    ToolCallStateChange change,
    ContextPaneNotifier contextNotifier,
  ) {
    if (change.isStarting) {
      contextNotifier.addToolExecution(change.toolName, isStarting: true);
    } else if (change.isEnding) {
      contextNotifier.addToolExecution(
        change.toolName,
        isStarting: false,
        success: change.isSuccess,
        error: change.error,
      );
    }
  }

  // State for tracking messages per AG-UI messageId
  // Maps AG-UI event messageId -> our internal ChatMessage id
  final Map<String, String> _messageIdMap = {};
  final Map<String, StringBuffer> _textBuffers = {};

  // Track processed UI tool calls to prevent duplicate execution
  final Set<String> _processedUiToolCalls = {};

  // Track processed tool notifications to prevent duplicates (key: "$toolCallId:$status")
  final Set<String> _processedToolNotifications = {};

  // Track tool call message IDs for updating status (key: toolCallId)
  final Map<String, String> _toolCallMessageIds = {};

  // Track active search widgets and their callbacks
  final Map<String, void Function(String, Map<String, dynamic>)> _searchCallbacks = {};

  // Track thinking message IDs (aguiThinkingId -> chatMessageId)
  final Map<String, String> _thinkingMessageIds = {};

  /// Process a single AG-UI event.
  void _processEvent(
    ag_ui.BaseEvent event,
    ChatNotifier chatNotifier,
    ContextPaneNotifier contextNotifier,
    CanvasNotifier canvasNotifier,
  ) {
    final activityNotifier = ref.read(activityStatusProvider.notifier);

    switch (event) {
      case ag_ui.RunStartedEvent():
        DebugLog.agui('RunStarted runId=${event.runId}');
        DebugLog.mapping('=== NEW RUN === messageIdMap has ${_messageIdMap.length} entries');
        contextNotifier.addAgUiEvent('Run Started', summary: event.runId);
        activityNotifier.startActivity();

      case ag_ui.TextMessageStartEvent():
        final aguiMessageId = event.messageId;
        DebugLog.mapping('TextMessageStart aguiId=$aguiMessageId, current map: $_messageIdMap');
        final chatMessageId = chatNotifier.startAgentMessage();
        _messageIdMap[aguiMessageId] = chatMessageId;
        _textBuffers[aguiMessageId] = StringBuffer();
        DebugLog.mapping('TextMessageStart mapped: aguiId=$aguiMessageId -> chatId=$chatMessageId');
        activityNotifier.handleEvent('TextMessageStart');

      case ag_ui.TextMessageContentEvent():
        final aguiMessageId = event.messageId;
        final chatMessageId = _messageIdMap[aguiMessageId];
        if (chatMessageId != null) {
          chatNotifier.appendToStreamingMessage(chatMessageId, event.delta);
          _textBuffers[aguiMessageId]?.write(event.delta);
        } else {
          DebugLog.warn('TextMessageContent: NO MAPPING for aguiId=$aguiMessageId, map=$_messageIdMap');
        }

      case ag_ui.TextMessageEndEvent():
        final aguiMessageId = event.messageId;
        final chatMessageId = _messageIdMap[aguiMessageId];
        DebugLog.mapping('TextMessageEnd aguiId=$aguiMessageId, chatId=$chatMessageId');
        if (chatMessageId != null) {
          chatNotifier.finalizeStreamingMessage(chatMessageId);
          final text = _textBuffers[aguiMessageId]?.toString() ?? '';
          DebugLog.chat('Finalized message: ${text.length} chars');
          contextNotifier.addTextMessage(text, isUser: false);
          _messageIdMap.remove(aguiMessageId);
          _textBuffers.remove(aguiMessageId);
        } else {
          DebugLog.warn('TextMessageEnd: NO MAPPING for aguiId=$aguiMessageId');
        }

      case ag_ui.ToolCallStartEvent():
        DebugLog.tool('ToolCallStart: ${event.toolCallName}');
        contextNotifier.addToolCall(event.toolCallName, summary: 'started');
        activityNotifier.handleEvent('ToolCallStart', toolName: event.toolCallName);

      case ag_ui.ToolCallArgsEvent():
        break; // Args handled by Thread class

      case ag_ui.ToolCallEndEvent():
        break;

      case ag_ui.ToolCallResultEvent():
        contextNotifier.addAgUiEvent('Tool Result');

      case ag_ui.StateSnapshotEvent():
        final stateData = event.snapshot as Map<String, dynamic>? ?? {};
        contextNotifier.updateState(stateData);

      case ag_ui.StateDeltaEvent():
        final delta = event.delta as List<dynamic>? ?? [];
        if (delta.isNotEmpty && delta.first is Map<String, dynamic>) {
          contextNotifier.applyDelta(delta.first as Map<String, dynamic>);
        }

      case ag_ui.ActivitySnapshotEvent():
        contextNotifier.addAgUiEvent(
          'Activity Snapshot',
          summary: '${event.activities.length} activities',
        );

      case ag_ui.ThinkingStartEvent():
        contextNotifier.addAgUiEvent('Thinking');
        activityNotifier.handleEvent('Thinking');

      case ag_ui.ThinkingTextMessageStartEvent():
        // Find the current or pending assistant message to attach thinking to
        // Look for the most recent agent message that's streaming or just started
        final chatMessages = ref.read(chatProvider).messages;
        ChatMessage? targetMessage;
        for (final m in chatMessages.reversed) {
          if (m.user.id == ChatUser.agent.id &&
              (m.isStreaming || m.type == MessageType.text)) {
            targetMessage = m;
            break;
          }
        }
        if (targetMessage != null) {
          chatNotifier.startThinking(targetMessage.id);
          // Track using a constant key since thinking events don't have messageId
          _thinkingMessageIds['current'] = targetMessage.id;
          DebugLog.agui('ThinkingTextMessageStart: attached to chatId=${targetMessage.id}');
        }

      case ag_ui.ThinkingTextMessageContentEvent():
        final chatMessageId = _thinkingMessageIds['current'];
        if (chatMessageId != null) {
          chatNotifier.appendThinking(chatMessageId, event.delta);
        }

      case ag_ui.ThinkingTextMessageEndEvent():
        final chatMessageId = _thinkingMessageIds['current'];
        if (chatMessageId != null) {
          chatNotifier.finalizeThinking(chatMessageId);
          _thinkingMessageIds.remove('current');
          DebugLog.agui('ThinkingTextMessageEnd: finalized chatId=$chatMessageId');
        }

      case ag_ui.ThinkingEndEvent():
        // Cleanup any orphaned thinking
        _thinkingMessageIds.remove('current');
        break;

      case ag_ui.RunFinishedEvent():
        DebugLog.agui('RunFinished runId=${event.runId}');
        DebugLog.mapping('=== RUN DONE === messageIdMap has ${_messageIdMap.length} entries remaining');
        contextNotifier.addAgUiEvent('Run Finished');
        activityNotifier.stopActivity();

      case ag_ui.RunErrorEvent():
        chatNotifier.addServerError(
          event.message,
          errorCode: event.code,
        );
        contextNotifier.addAgUiEvent('Error', summary: event.message);
        DebugLog.error('RunError: ${event.code}: ${event.message}');
        activityNotifier.stopActivity();

      case ag_ui.CustomEvent():
        _handleCustomEvent(
          event,
          chatNotifier,
          contextNotifier,
          canvasNotifier,
        );

      default:
        DebugLog.warn('Unhandled event: ${event.runtimeType}');
    }
  }

  /// Handle UI tools (canvas_render, genui_render) that need Riverpod access.
  Map<String, dynamic> _handleUiTool(
    String toolName,
    Map<String, dynamic> args,
    ChatNotifier chatNotifier,
    CanvasNotifier canvasNotifier,
    ContextPaneNotifier contextNotifier,
  ) {
    if (toolName == 'genui_render') {
      final widgetName = args['widget_name'] as String? ?? 'Widget';
      final data = args['data'] as Map<String, dynamic>? ?? {};

      chatNotifier.addGenUiMessage(
        GenUiContent(
          toolCallId: 'tool-${DateTime.now().millisecondsSinceEpoch}',
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
          break;
        case 'replace':
          canvasNotifier.replaceAll(widgetName, data);
          break;
        default:
          canvasNotifier.addItem(widgetName, data);
      }
      contextNotifier.addCanvasRender(widgetName, position);
      return {'rendered': true, 'widget': widgetName, 'position': position};
    }

    return {'error': 'Unknown UI tool: $toolName'};
  }

  /// Handle custom events (genui_render, canvas_render).
  /// NOTE: These are now handled via uiToolHandler, so CustomEvents are ignored
  /// to prevent double-rendering.
  void _handleCustomEvent(
    ag_ui.CustomEvent event,
    ChatNotifier chatNotifier,
    ContextPaneNotifier contextNotifier,
    CanvasNotifier canvasNotifier,
  ) {
    // genui_render and canvas_render are handled via _handleUiTool
    // CustomEvents for these are ignored to prevent double-rendering
  }

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

  /// Stubbed staff skills data (keyed by person ID)
  static const Map<String, Map<String, dynamic>> _stubbedStaffSkills = {
    'u1': {
      'person_id': 'u1',
      'name': 'John Smith',
      'title': 'Engineering Lead',
      'skills': [
        {'name': 'Flutter', 'level': 5},
        {'name': 'Dart', 'level': 5},
        {'name': 'Python', 'level': 4},
        {'name': 'AWS', 'level': 3},
        {'name': 'Leadership', 'level': 4},
      ],
    },
    'u2': {
      'person_id': 'u2',
      'name': 'Jane Doe',
      'title': 'Product Manager',
      'skills': [
        {'name': 'Product Strategy', 'level': 5},
        {'name': 'Agile', 'level': 4},
        {'name': 'Data Analysis', 'level': 3},
        {'name': 'UX Research', 'level': 4},
      ],
    },
    'u3': {
      'person_id': 'u3',
      'name': 'Bob Wilson',
      'title': 'Senior Developer',
      'skills': [
        {'name': 'Python', 'level': 5},
        {'name': 'Django', 'level': 5},
        {'name': 'PostgreSQL', 'level': 4},
        {'name': 'Docker', 'level': 4},
        {'name': 'AWS', 'level': 3},
      ],
    },
    'u4': {
      'person_id': 'u4',
      'name': 'Alice Johnson',
      'title': 'UX Designer',
      'skills': [
        {'name': 'Figma', 'level': 5},
        {'name': 'User Research', 'level': 4},
        {'name': 'Prototyping', 'level': 5},
        {'name': 'CSS', 'level': 3},
      ],
    },
    'u5': {
      'person_id': 'u5',
      'name': 'Charlie Brown',
      'title': 'DevOps Engineer',
      'skills': [
        {'name': 'Kubernetes', 'level': 5},
        {'name': 'Docker', 'level': 5},
        {'name': 'AWS', 'level': 5},
        {'name': 'Terraform', 'level': 4},
        {'name': 'Python', 'level': 3},
      ],
    },
    'u6': {
      'person_id': 'u6',
      'name': 'Diana Prince',
      'title': 'QA Lead',
      'skills': [
        {'name': 'Test Automation', 'level': 5},
        {'name': 'Selenium', 'level': 4},
        {'name': 'Python', 'level': 4},
        {'name': 'API Testing', 'level': 5},
      ],
    },
    'u7': {
      'person_id': 'u7',
      'name': 'Edward Norton',
      'title': 'Backend Developer',
      'skills': [
        {'name': 'Java', 'level': 5},
        {'name': 'Spring Boot', 'level': 5},
        {'name': 'PostgreSQL', 'level': 4},
        {'name': 'Redis', 'level': 4},
        {'name': 'Kafka', 'level': 3},
      ],
    },
    'u8': {
      'person_id': 'u8',
      'name': 'Fiona Apple',
      'title': 'Frontend Developer',
      'skills': [
        {'name': 'React', 'level': 5},
        {'name': 'TypeScript', 'level': 5},
        {'name': 'CSS', 'level': 4},
        {'name': 'Flutter', 'level': 3},
      ],
    },
    'u9': {
      'person_id': 'u9',
      'name': 'George Lucas',
      'title': 'Data Scientist',
      'skills': [
        {'name': 'Python', 'level': 5},
        {'name': 'Machine Learning', 'level': 5},
        {'name': 'TensorFlow', 'level': 4},
        {'name': 'SQL', 'level': 4},
        {'name': 'Data Viz', 'level': 4},
      ],
    },
    'u10': {
      'person_id': 'u10',
      'name': 'Hannah Montana',
      'title': 'Marketing Manager',
      'skills': [
        {'name': 'Digital Marketing', 'level': 5},
        {'name': 'SEO', 'level': 4},
        {'name': 'Analytics', 'level': 4},
        {'name': 'Content Strategy', 'level': 5},
      ],
    },
  };

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
    {
      'id': 'p4',
      'title': 'API Gateway Modernization',
      'description': 'Replace monolithic API with microservices architecture',
      'required_skills': ['Java', 'Spring Boot', 'Kubernetes', 'Kafka'],
      'status': 'open',
    },
    {
      'id': 'p5',
      'title': 'Marketing Analytics Dashboard',
      'description': 'Real-time dashboard for marketing campaign performance',
      'required_skills': ['React', 'TypeScript', 'Data Viz', 'Analytics'],
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
        '4. The LLM will show SkillsCards for recommended team members',
        '5. Try: "Pin these to the canvas" to save them',
      ],
    },
    'skill-match': {
      'title': 'Skill Matching',
      'description': 'Find the best project fit for selected staff members',
      'steps': [
        '1. Type: /search staff',
        '2. Select 2-3 people (e.g., John Smith, Bob Wilson)',
        '3. Complete the message: "Show their skills"',
        '4. Then ask: "Which projects are these people best suited for?"',
        '5. LLM shows ProjectCards with matched_skills highlighted',
      ],
    },
    'gap-analysis': {
      'title': 'Skill Gap Analysis',
      'description': 'Identify missing skills for a project',
      'steps': [
        '1. Type: /list projects',
        '2. Say: "What skills are we missing for the API Gateway project?"',
        '3. LLM analyzes staff skills vs project requirements',
        '4. Shows which required skills have no expert available',
        '5. Try: "Who should we hire to fill these gaps?"',
      ],
    },
    'compare': {
      'title': 'Staff Comparison',
      'description': 'Compare candidates for a specific role or project',
      'steps': [
        '1. Type: /search staff',
        '2. Select 2 people to compare',
        '3. Say: "Compare these two for the ML Recommendation Engine project"',
        '4. LLM shows side-by-side skills with match percentages',
        '5. Ask: "Who would you recommend and why?"',
      ],
    },
    'coverage': {
      'title': 'Project Coverage Ranking',
      'description': 'Rank projects by how well current staff can cover them',
      'steps': [
        '1. Say: "Rank all projects by how well we can staff them"',
        '2. LLM analyzes all staff skills vs all project requirements',
        '3. Shows ProjectCards sorted by skill coverage percentage',
        '4. Try: "What would it take to fully staff the bottom-ranked project?"',
      ],
    },
  };

  /// Handle slash commands locally (not sent to backend).
  /// Returns true if command was handled, false to send to backend.
  bool _handleSlashCommand(
    String text,
    ChatNotifier chatNotifier,
    CanvasNotifier canvasNotifier,
  ) {
    final parts = text.split(' ');
    final command = parts[0].toLowerCase();
    final args = parts.skip(1).toList();

    switch (command) {
      case '/search':
        final searchType = args.isNotEmpty ? args[0] : 'items';
        _showSearchWidget(searchType, chatNotifier, canvasNotifier);
        return true;

      case '/list':
        final listType = args.isNotEmpty ? args[0] : 'items';
        _showListWidget(listType, chatNotifier, canvasNotifier);
        return true;

      case '/demo':
        final demoName = args.isNotEmpty ? args.join('-') : '';
        _showDemo(demoName, chatNotifier);
        return true;

      case '/canvas':
        _showCanvasState(chatNotifier, canvasNotifier);
        return true;

      case '/help':
        chatNotifier.addSystemMessage(
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
        // Unknown command - let it go to backend
        return false;
    }
  }

  /// Show a search widget in the chat for interactive selection.
  void _showSearchWidget(
    String searchType,
    ChatNotifier chatNotifier,
    CanvasNotifier canvasNotifier,
  ) {
    // Show user's command in chat
    chatNotifier.addUserMessage('/search $searchType');

    // Determine items based on search type
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

    // Generate unique ID for this search widget
    final searchId = 'search-${DateTime.now().millisecondsSinceEpoch}';

    // Store callback for this search widget
    _searchCallbacks[searchId] = (eventName, payload) {
      _handleSearchWidgetEvent(eventName, payload, searchType, chatNotifier);
      // Clean up callback after terminal events
      if (eventName == 'submit' || eventName == 'cancel') {
        _searchCallbacks.remove(searchId);
      }
    };

    // Add SearchWidget as a GenUI message
    // Include _toolCallId in data so widget can pass it back with events
    chatNotifier.addGenUiMessage(
      GenUiContent(
        toolCallId: searchId,
        widgetName: 'SearchWidget',
        data: {
          '_toolCallId': searchId,  // For event routing
          'placeholder': placeholder,
          'multi_select': true,
          'items': items,
          'search_type': searchType,
        },
      ),
    );
  }

  /// Show a list widget in the chat (e.g., projects, demos).
  void _showListWidget(
    String listType,
    ChatNotifier chatNotifier,
    CanvasNotifier canvasNotifier,
  ) {
    // Show user's command in chat
    chatNotifier.addUserMessage('/list $listType');

    switch (listType) {
      case 'projects':
        // Show each project as a ProjectCard in chat
        for (final project in _stubbedProjectsData) {
          chatNotifier.addGenUiMessage(
            GenUiContent(
              toolCallId: 'project-${project['id']}-${DateTime.now().millisecondsSinceEpoch}',
              widgetName: 'ProjectCard',
              data: project,
            ),
          );
        }
      case 'demos':
        // Show available demos as a formatted list
        final demoList = _demos.entries.map((e) {
          final demo = e.value;
          return '• /demo ${e.key} - ${demo['title']}\n  ${demo['description']}';
        }).join('\n\n');
        chatNotifier.addSystemMessage('Available Demos:\n\n$demoList');
      default:
        chatNotifier.addSystemMessage('Unknown list type: $listType\nTry: /list projects or /list demos');
    }
  }

  /// Show current canvas state.
  void _showCanvasState(ChatNotifier chatNotifier, CanvasNotifier canvasNotifier) {
    chatNotifier.addUserMessage('/canvas');

    final canvasState = ref.read(canvasProvider);
    chatNotifier.addSystemMessage(canvasState.toSummary());
  }

  /// Show a specific demo walkthrough.
  void _showDemo(String demoName, ChatNotifier chatNotifier) {
    chatNotifier.addUserMessage('/demo $demoName');

    if (demoName.isEmpty) {
      chatNotifier.addSystemMessage('Usage: /demo <name>\nType /list demos to see available demos.');
      return;
    }

    final demo = _demos[demoName];
    if (demo == null) {
      final available = _demos.keys.join(', ');
      chatNotifier.addSystemMessage('Unknown demo: $demoName\nAvailable: $available');
      return;
    }

    final steps = (demo['steps'] as List<dynamic>).join('\n');
    chatNotifier.addSystemMessage(
      '${demo['title']}\n'
      '${'-' * (demo['title'] as String).length}\n'
      '${demo['description']}\n\n'
      'Walkthrough:\n$steps',
    );
  }

  /// Handle events from SearchWidget.
  void _handleSearchWidgetEvent(
    String eventName,
    Map<String, dynamic> payload,
    String searchType,
    ChatNotifier chatNotifier,
  ) {
    switch (eventName) {
      case 'submit':
        final selected = payload['selected'] as List<dynamic>? ?? [];
        if (selected.isNotEmpty) {
          // Format selection as text to pre-fill the input
          final names = selected.map((item) {
            final map = item as Map<String, dynamic>;
            return '${map['title']} (${map['subtitle']})';
          }).join(', ');

          // Pre-fill the input with selection, let user complete the message
          final prefill = 'Selected $searchType: $names\n';
          _inputController.text = prefill;
          // Move cursor to end so user can continue typing
          _inputController.selection = TextSelection.fromPosition(
            TextPosition(offset: prefill.length),
          );
        }

      case 'cancel':
        chatNotifier.addSystemMessage('Search cancelled.');
    }
  }

  /// Paste from clipboard into input field.
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

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatProvider);

    // Convert our messages to Dash Chat format
    final dashMessages = chatState.messages.reversed
        .map((m) => toDashChatMessage(m))
        .toList();

    // Wrap with keyboard shortcuts (Cmd+K for paste, Cmd+F for search)
    return Shortcuts(
      shortcuts: {
        LogicalKeySet(LogicalKeyboardKey.meta, LogicalKeyboardKey.keyK):
            const _PasteIntent(),
        LogicalKeySet(LogicalKeyboardKey.meta, LogicalKeyboardKey.keyF):
            const _SearchIntent(),
      },
      child: Actions(
        actions: {
          _PasteIntent: CallbackAction<_PasteIntent>(
            onInvoke: (_) {
              _pasteFromClipboard();
              return null;
            },
          ),
          _SearchIntent: CallbackAction<_SearchIntent>(
            onInvoke: (_) {
              ref.read(chatSearchProvider.notifier).openSearch();
              return null;
            },
          ),
        },
        child: Focus(
          autofocus: true,
          child: LayoutBuilder(
      builder: (context, constraints) {
        // Constrain message bubbles to 70% of available chat width
        final messageMaxWidth = constraints.maxWidth * 0.7;

        final activityStatus = ref.watch(activityStatusProvider);
        final searchState = ref.watch(chatSearchProvider);
        final selectedRoom = ref.watch(selectedRoomDataProvider);
        final selectedRoomId = ref.watch(selectedRoomProvider);
        final hasMessages = chatState.messages.isNotEmpty;

        // Focus input when room changes
        _checkRoomChange(selectedRoomId);

        return Column(
          children: [
            // Search bar (when active)
            if (searchState.isActive)
              ChatSearchBar(
                messageIds: chatState.messages.map((m) => m.id).toList(),
                getMessageText: (id) {
                  try {
                    final msg = chatState.messages.firstWhere((m) => m.id == id);
                    return msg.text ?? '';
                  } catch (_) {
                    return '';
                  }
                },
              ),
            // Chat messages area (with DashChat's input hidden)
            Expanded(
              child: Stack(
                children: [
                  dash.DashChat(
          currentUser: dash.ChatUser(
            id: ChatUser.user.id,
            firstName: ChatUser.user.firstName,
          ),
          onSend: _handleSend,
          messages: dashMessages,
          messageOptions: dash.MessageOptions(
            showCurrentUserAvatar: false,
            showOtherUsersAvatar: true,
            messageDecorationBuilder: (message, previousMessage, nextMessage) {
              final isUser = message.user.id == ChatUser.user.id;
              return BoxDecoration(
                color: isUser
                    ? Theme.of(context).colorScheme.primaryContainer
                    : Theme.of(context).colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(12),
              );
            },
            // Constrain message width to 70% of actual available space
            maxWidth: messageMaxWidth,
            messageTextBuilder: (message, previousMessage, nextMessage) {
          final customProps = message.customProperties;
          final chatMessage = customProps?['chatMessage'] as ChatMessage?;
          final isAgentMessage = message.user.id == ChatUser.agent.id;

          // For non-text messages, build custom widget
          if (chatMessage != null && chatMessage.type != MessageType.text) {
            final customWidget = _messageBuilder.build(
              message,
              previousMessage: previousMessage,
              nextMessage: nextMessage,
              isAfterDateSeparator: false,
              isBeforeDateSeparator: false,
            );
            if (customWidget != null) {
              // Add feedback chips and copy for agent messages (not for tool calls/loading)
              if (isAgentMessage &&
                  chatMessage.type != MessageType.toolCall &&
                  chatMessage.type != MessageType.loading) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    customWidget,
                    _MessageActionsRow(
                      messageId: chatMessage.id,
                      messageText: message.text,
                    ),
                  ],
                );
              }
              return customWidget;
            }
          }

          // Default text rendering with feedback chips for agent messages
          final textStyle = TextStyle(
            color: message.user.id == ChatUser.user.id
                ? Theme.of(context).colorScheme.onPrimaryContainer
                : Theme.of(context).colorScheme.onSurface,
          );
          final textWidget = StreamingMarkdownWidget(
            text: message.text,
            messageId: chatMessage?.id ?? message.createdAt.toString(),
            isStreaming: chatMessage?.isStreaming ?? false,
            textStyle: textStyle,
            onQuote: (quotedText) {
              // Insert quoted text into input field
              final currentText = _inputController.text;
              final newText = currentText.isEmpty
                  ? '$quotedText\n\n'
                  : '$currentText\n\n$quotedText\n\n';
              _inputController.text = newText;
              _inputController.selection = TextSelection.collapsed(
                offset: newText.length,
              );
            },
          );

          // Build thinking section if present
          Widget? thinkingSection;
          if (isAgentMessage &&
              chatMessage != null &&
              chatMessage.thinkingText != null &&
              chatMessage.thinkingText!.isNotEmpty) {
            thinkingSection = CollapsibleThinkingWidget(
              thinkingText: chatMessage.thinkingText!,
              isStreaming: chatMessage.isThinkingStreaming,
              isExpanded: chatMessage.isThinkingExpanded || chatMessage.isThinkingStreaming,
              onToggle: () {
                ref.read(chatProvider.notifier).toggleThinkingExpanded(chatMessage.id);
              },
            );
          }

          // Build tool calls section if present (attached to message)
          Widget? toolCallsSection;
          if (isAgentMessage &&
              chatMessage != null &&
              chatMessage.toolCalls != null &&
              chatMessage.toolCalls!.isNotEmpty) {
            toolCallsSection = ToolCallSummaryWidget(
              toolCalls: chatMessage.toolCalls!,
              isExpanded: chatMessage.isToolGroupExpanded,
              onToggle: () {
                ref.read(chatProvider.notifier).toggleToolGroupExpanded(chatMessage.id);
              },
            );
          }

          // Add feedback chips and copy button for finalized agent text messages
          if (isAgentMessage && chatMessage != null && !chatMessage.isStreaming) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                if (thinkingSection != null) thinkingSection,
                textWidget,
                if (toolCallsSection != null) toolCallsSection,
                _MessageActionsRow(
                  messageId: chatMessage.id,
                  messageText: message.text,
                ),
              ],
            );
          }

          // Streaming agent message with thinking
          if (isAgentMessage && chatMessage != null && thinkingSection != null) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                thinkingSection,
                textWidget,
              ],
            );
          }

          return textWidget;
        },
      ),
      messageListOptions: dash.MessageListOptions(
        onLoadEarlier: () async {
          // TODO: Implement pagination if needed
        },
      ),
      // Hide DashChat's input - we use ChatInputArea instead
      inputOptions: dash.InputOptions(
        textController: _inputController,
        sendOnEnter: false,
        alwaysShowSend: false,
        inputDecoration: const InputDecoration(
          // Make input invisible
          border: InputBorder.none,
          contentPadding: EdgeInsets.zero,
          isDense: true,
          constraints: BoxConstraints(maxHeight: 0),
        ),
        inputToolbarPadding: EdgeInsets.zero,
        sendButtonBuilder: (onSend) => const SizedBox.shrink(),
      ),
          typingUsers: chatState.isAgentTyping
              ? [
                  dash.ChatUser(
                    id: ChatUser.agent.id,
                    firstName: ChatUser.agent.firstName,
                  ),
                ]
              : [],
            ),
                  // Cover DashChat's input area (it can't be fully hidden via InputOptions)
                  Positioned(
                    left: 0,
                    right: 0,
                    bottom: 0,
                    height: 64,
                    child: Container(
                      color: Theme.of(context).colorScheme.surface,
                    ),
                  ),
                ],
              ),
            ),
            // Activity status bar OR custom input area
            if (activityStatus.isActive && activityStatus.currentMessage != null)
              ActivityStatusBar(
                message: activityStatus.currentMessage!,
                onStop: () async {
                  final agUiService = ref.read(configuredAgUiServiceProvider);
                  final roomId = agUiService.currentRoomId;
                  if (roomId != null) {
                    DebugLog.network('Stop button: cancelling run for room $roomId');
                    final connectionManager = ref.read(connectionManagerProvider);
                    await connectionManager.cancelRun(roomId);
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
                hasMessages: hasMessages,
                isLoading: activityStatus.isActive,
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

/// Intent for search action.
class _SearchIntent extends Intent {
  const _SearchIntent();
}

/// Row with feedback chips and copy button for messages.
class _MessageActionsRow extends ConsumerStatefulWidget {
  final String messageId;
  final String messageText;

  const _MessageActionsRow({
    required this.messageId,
    required this.messageText,
  });

  @override
  ConsumerState<_MessageActionsRow> createState() => _MessageActionsRowState();
}

class _MessageActionsRowState extends ConsumerState<_MessageActionsRow> {
  bool _copied = false;

  Future<void> _copyToClipboard() async {
    await Clipboard.setData(ClipboardData(text: widget.messageText));
    setState(() => _copied = true);
    // Reset after brief delay
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _copied = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Feedback chips
          MessageFeedbackChips(messageId: widget.messageId),
          const Spacer(),
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
                  color: _copied
                      ? Colors.green
                      : Theme.of(context).colorScheme.outline,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
