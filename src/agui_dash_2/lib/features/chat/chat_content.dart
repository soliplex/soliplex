import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:dash_chat_2/dash_chat_2.dart' as dash;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/models/chat_models.dart';
import '../../core/services/agui_service.dart';
import '../../core/services/canvas_service.dart';
import '../../core/services/chat_service.dart';
import '../../core/services/context_pane_service.dart';
import '../../core/services/local_tools_service.dart';
import '../../core/services/tool_execution_service.dart';
import '../../infrastructure/quick_agui/tool_call_state.dart';
import 'builders/message_builder.dart';
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
    debugPrint('GenUI Event: $eventName, args: $arguments');

    // Check if this event has a toolCallId that matches a registered callback
    final toolCallId = arguments['_toolCallId'] as String?;
    if (toolCallId != null && _searchCallbacks.containsKey(toolCallId)) {
      final callback = _searchCallbacks[toolCallId];
      final payload = Map<String, dynamic>.from(arguments);
      payload.remove('_toolCallId');
      callback?.call(eventName, payload);
      return;
    }

    // Default: show snackbar for other events
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Event: $eventName'),
          duration: const Duration(seconds: 2),
        ),
      );
    }
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
      chatNotifier.addErrorMessage('AG-UI server not configured');
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
          debugPrint('UI Tool Handler: $toolName (id=$toolCallId) with args: $args');

          // Prevent duplicate execution of the same tool call
          if (_processedUiToolCalls.contains(toolCallId)) {
            debugPrint('UI Tool Handler: SKIPPING duplicate tool call $toolCallId');
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
          debugPrint('onLocalToolExecution: toolCallId=$toolCallId, toolName=$toolName, status=$status');

          // Deduplicate by tool call ID - skip if we've already processed this execution
          final trackingKey = '$toolCallId:$status';
          if (_processedToolNotifications.contains(trackingKey)) {
            debugPrint('Skipping duplicate tool notification: $toolCallId $toolName $status');
            return;
          }
          _processedToolNotifications.add(trackingKey);

          contextNotifier.addLocalToolExecution(toolName, status: status);

          // Add or update tool call message in chat
          if (status == 'executing') {
            final messageId = chatNotifier.addToolCallMessage(toolName);
            _toolCallMessageIds[toolCallId] = messageId;
            debugPrint('Added tool call message: toolCallId=$toolCallId -> messageId=$messageId');
          } else {
            final messageId = _toolCallMessageIds[toolCallId];
            debugPrint('Updating tool call: toolCallId=$toolCallId, messageId=$messageId');
            if (messageId != null) {
              chatNotifier.updateToolCallStatus(messageId, status);
              debugPrint('Updated tool call status to: $status');
              if (status == 'completed' || status.startsWith('error')) {
                _toolCallMessageIds.remove(toolCallId);
              }
            } else {
              debugPrint('WARNING: No message ID found for toolCallId=$toolCallId');
            }
          }
        },
        onToolStateChange: (change) {
          if (!mounted) return;
          _handleToolStateChange(change, toolExecutionNotifier, contextNotifier, chatNotifier);
        },
      );
    } catch (e) {
      debugPrint('Error sending message: $e');
      if (mounted) {
        chatNotifier.addErrorMessage('Error: $e');
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
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
    debugPrint(
      'AG-UI: Tool state change - ${change.toolName}: ${change.previousState} -> ${change.newState}',
    );

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
    // Skip verbose thinking content events
    if (event is! ag_ui.ThinkingTextMessageContentEvent) {
      debugPrint('AG-UI Event: ${event.runtimeType}');
    }

    switch (event) {
      case ag_ui.RunStartedEvent():
        debugPrint('AG-UI: Run started - ${event.runId}');
        contextNotifier.addAgUiEvent('Run Started', summary: event.runId);

      case ag_ui.TextMessageStartEvent():
        final aguiMessageId = event.messageId;
        debugPrint('AG-UI: TextMessageStartEvent received, messageId=$aguiMessageId');
        final chatMessageId = chatNotifier.startAgentMessage();
        _messageIdMap[aguiMessageId] = chatMessageId;
        _textBuffers[aguiMessageId] = StringBuffer();
        debugPrint('AG-UI: Text message started, aguiId=$aguiMessageId -> chatId=$chatMessageId');

      case ag_ui.TextMessageContentEvent():
        final aguiMessageId = event.messageId;
        final chatMessageId = _messageIdMap[aguiMessageId];
        debugPrint('AG-UI: TextMessageContentEvent received, messageId=$aguiMessageId, delta="${event.delta}"');
        if (chatMessageId != null) {
          chatNotifier.appendToStreamingMessage(chatMessageId, event.delta);
          _textBuffers[aguiMessageId]?.write(event.delta);
        } else {
          debugPrint('AG-UI: WARNING - TextMessageContentEvent but no mapping for messageId=$aguiMessageId');
        }

      case ag_ui.TextMessageEndEvent():
        final aguiMessageId = event.messageId;
        final chatMessageId = _messageIdMap[aguiMessageId];
        debugPrint('AG-UI: TextMessageEndEvent received, messageId=$aguiMessageId');
        if (chatMessageId != null) {
          chatNotifier.finalizeStreamingMessage(chatMessageId);
          final text = _textBuffers[aguiMessageId]?.toString() ?? '';
          contextNotifier.addTextMessage(text, isUser: false);
          _messageIdMap.remove(aguiMessageId);
          _textBuffers.remove(aguiMessageId);
        } else {
          debugPrint('AG-UI: WARNING - TextMessageEndEvent but no mapping for messageId=$aguiMessageId');
        }

      case ag_ui.ToolCallStartEvent():
        debugPrint('AG-UI: Tool call started - ${event.toolCallName}');
        contextNotifier.addToolCall(event.toolCallName, summary: 'started');

      case ag_ui.ToolCallArgsEvent():
        // Args are handled by Thread class, just log here
        debugPrint('AG-UI: Tool call args - ${event.toolCallId}');

      case ag_ui.ToolCallEndEvent():
        debugPrint('AG-UI: Tool call ended - ${event.toolCallId}');

      case ag_ui.ToolCallResultEvent():
        debugPrint('AG-UI: Tool result received');
        contextNotifier.addAgUiEvent('Tool Result');

      case ag_ui.StateSnapshotEvent():
        debugPrint('AG-UI: State snapshot received');
        final stateData = event.snapshot as Map<String, dynamic>? ?? {};
        contextNotifier.updateState(stateData);

      case ag_ui.StateDeltaEvent():
        debugPrint('AG-UI: State delta received');
        final delta = event.delta as List<dynamic>? ?? [];
        if (delta.isNotEmpty && delta.first is Map<String, dynamic>) {
          contextNotifier.applyDelta(delta.first as Map<String, dynamic>);
        }

      case ag_ui.ActivitySnapshotEvent():
        debugPrint(
          'AG-UI: Activity snapshot received - ${event.activities.length} activities',
        );
        contextNotifier.addAgUiEvent(
          'Activity Snapshot',
          summary: '${event.activities.length} activities',
        );

      case ag_ui.ThinkingStartEvent():
        debugPrint('AG-UI: Thinking started');
        contextNotifier.addAgUiEvent('Thinking');

      case ag_ui.ThinkingTextMessageStartEvent():
        debugPrint('AG-UI: Thinking text started');

      case ag_ui.ThinkingTextMessageContentEvent():
        // Suppressed - too verbose
        break;

      case ag_ui.ThinkingTextMessageEndEvent():
        debugPrint('AG-UI: Thinking text ended');

      case ag_ui.ThinkingEndEvent():
        debugPrint('AG-UI: Thinking ended');

      case ag_ui.RunFinishedEvent():
        debugPrint('AG-UI: Run finished - ${event.runId}');
        contextNotifier.addAgUiEvent('Run Finished');

      case ag_ui.RunErrorEvent():
        chatNotifier.addErrorMessage(event.message);
        contextNotifier.addAgUiEvent('Error', summary: event.message);
        debugPrint('AG-UI: Run error - ${event.code}: ${event.message}');

      // Handle custom events for genui_render and canvas_render
      case ag_ui.CustomEvent():
        _handleCustomEvent(
          event,
          chatNotifier,
          contextNotifier,
          canvasNotifier,
        );

      default:
        debugPrint('AG-UI: Unhandled event - ${event.runtimeType}: $event');
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
    debugPrint('_handleUiTool: $toolName');

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

      debugPrint(
        '_handleUiTool canvas_render: widget=$widgetName, position=$position',
      );

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
    final eventName = event.name;

    debugPrint('AG-UI: Custom event - $eventName (ignored - handled via tool)');

    // genui_render and canvas_render are handled via _handleUiTool
    // CustomEvents for these are ignored to prevent double-rendering
    if (eventName == 'genui_render' || eventName == 'canvas_render') {
      return;
    }
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
    debugPrint('SearchWidget event: $eventName, payload: $payload');

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

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatProvider);

    // Convert our messages to Dash Chat format
    final dashMessages = chatState.messages.reversed
        .map((m) => toDashChatMessage(m))
        .toList();

    // Use LayoutBuilder to get actual available width for the chat column
    return LayoutBuilder(
      builder: (context, constraints) {
        // Constrain message bubbles to 70% of available chat width
        final messageMaxWidth = constraints.maxWidth * 0.7;

        return Column(
          children: [
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

          // For non-text messages, build custom widget
          if (chatMessage != null && chatMessage.type != MessageType.text) {
            debugPrint('messageTextBuilder: Rendering ${chatMessage.type}');
            final customWidget = _messageBuilder.build(
              message,
              previousMessage: previousMessage,
              nextMessage: nextMessage,
              isAfterDateSeparator: false,
              isBeforeDateSeparator: false,
            );
            if (customWidget != null) {
              return customWidget;
            }
          }

          // Default text rendering
          return Text(
            message.text,
            style: TextStyle(
              color: message.user.id == ChatUser.user.id
                  ? Theme.of(context).colorScheme.onPrimaryContainer
                  : Theme.of(context).colorScheme.onSurface,
            ),
          );
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
        );
      },
    );
  }
}
