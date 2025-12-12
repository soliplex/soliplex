import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:dash_chat_2/dash_chat_2.dart' as dash;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/models/chat_models.dart';
import '../../core/services/activity_status_service.dart';
import '../../core/services/agui_service.dart';
import '../../core/services/chat_search_service.dart';
import '../../core/services/canvas_service.dart';
import '../../core/services/chat_service.dart';
import '../../core/services/context_pane_service.dart';
import '../../core/services/local_tools_service.dart';
import '../../core/services/tool_execution_service.dart';
import '../../core/utils/debug_log.dart';
import '../../infrastructure/quick_agui/tool_call_state.dart';
import 'builders/message_builder.dart';
import 'widgets/chat_search_bar.dart';
import 'widgets/code_block_widget.dart';
import 'widgets/message_feedback_chips.dart';
import 'widgets/streaming_markdown_widget.dart';
import 'widgets/tool_execution_indicator.dart';

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

  @override
  void initState() {
    super.initState();
    _messageBuilder = MessageBuilder(onGenUiEvent: _handleGenUiEvent);
  }

  @override
  void dispose() {
    _inputController.dispose();
    super.dispose();
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

  Future<void> _handleSend(dash.ChatMessage dashMessage) async {
    final text = dashMessage.text.trim();
    if (text.isEmpty) return;

    // Clear input immediately after capturing text
    _inputController.clear();

    final chatNotifier = ref.read(chatProvider.notifier);
    final agUiService = ref.read(configuredAgUiServiceProvider);
    final localToolsService = ref.read(localToolsServiceProvider);
    final contextNotifier = ref.read(contextPaneProvider.notifier);
    final canvasNotifier = ref.read(canvasProvider.notifier);
    final toolExecutionNotifier = ref.read(toolExecutionProvider.notifier);

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
          _handleToolStateChange(change, toolExecutionNotifier, contextNotifier, chatNotifier);
        },
      );
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
      }
    } finally {
      // Ensure tool execution state is cleared when chat completes
      if (mounted) {
        toolExecutionNotifier.clearAll();
      }
    }
  }

  /// Handle tool call state changes for UI notifications.
  ///
  /// Note: Tool call messages are added/updated via onLocalToolExecution callback.
  /// This handler only manages the ToolExecutionNotifier (for the indicator widget)
  /// and ContextPaneNotifier (for the context pane).
  void _handleToolStateChange(
    ToolCallStateChange change,
    ToolExecutionNotifier toolExecutionNotifier,
    ContextPaneNotifier contextNotifier,
    ChatNotifier chatNotifier,
  ) {
    if (change.isStarting) {
      // Tool execution started
      toolExecutionNotifier.startExecution(change.toolCallId, change.toolName);
      contextNotifier.addToolExecution(change.toolName, isStarting: true);
      // Note: Chat message is added via onLocalToolExecution to track ID for status updates
    } else if (change.isEnding) {
      // Tool execution ended
      toolExecutionNotifier.endExecution(change.toolCallId);
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
        break;

      case ag_ui.ThinkingTextMessageContentEvent():
        break;

      case ag_ui.ThinkingTextMessageEndEvent():
        break;

      case ag_ui.ThinkingEndEvent():
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

        return Stack(
          children: [
            Column(
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
                // Tool execution indicator at top
                const ToolExecutionIndicator(),
                // Chat area takes remaining space
                Expanded(
                  child: dash.DashChat(
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

          // Add feedback chips and copy button for finalized agent text messages
          if (isAgentMessage && chatMessage != null && !chatMessage.isStreaming) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                textWidget,
                _MessageActionsRow(
                  messageId: chatMessage.id,
                  messageText: message.text,
                ),
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
      inputOptions: dash.InputOptions(
        textController: _inputController,
        sendOnEnter: true,
        inputDecoration: InputDecoration(
          hintText: 'Type a message, SHIFT+ENTER multiple lines',
          filled: true,
          fillColor: Theme.of(context).colorScheme.surfaceContainerHighest,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(24),
            borderSide: BorderSide.none,
          ),
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 20,
            vertical: 12,
          ),
        ),
        sendButtonBuilder: (onSend) {
          return IconButton(
            icon: const Icon(Icons.send),
            onPressed: onSend,
            color: Theme.of(context).colorScheme.primary,
          );
        },
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
            ),
              ],
            ),
            // Activity status overlay (covers input area when active)
            if (activityStatus.isActive && activityStatus.currentMessage != null)
              Positioned(
                left: 0,
                right: 0,
                bottom: 0,
                child: Container(
                  padding: const EdgeInsets.all(8),
                  color: Theme.of(context).colorScheme.surface,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.surfaceContainerHighest,
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
                            activityStatus.currentMessage!,
                            key: ValueKey(activityStatus.currentMessage),
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.onSurfaceVariant,
                              fontSize: 14,
                            ),
                          ),
                        ),
                        const Spacer(),
                        // Stop button (non-functional)
                        IconButton(
                          icon: const Icon(Icons.stop_circle_outlined),
                          onPressed: () {
                            // TODO: Implement stop functionality
                            debugPrint('Stop button pressed (not yet implemented)');
                          },
                          tooltip: 'Stop generation',
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ],
                    ),
                  ),
                ),
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
                color: Theme.of(context)
                    .colorScheme
                    .primary
                    .withAlpha((opacity * 255).round()),
              ),
            );
          },
        );
      }),
    );
  }

  /// Simple sin approximation using Taylor series.
  double _sin(double x) {
    x = x % (2 * 3.14159);
    if (x > 3.14159) x -= 2 * 3.14159;
    double result = x;
    double term = x;
    for (int i = 1; i <= 5; i++) {
      term *= -x * x / ((2 * i) * (2 * i + 1));
      result += term;
    }
    return result;
  }
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
