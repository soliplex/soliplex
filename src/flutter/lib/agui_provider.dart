import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter/foundation.dart';
import 'package:flutter_ai_toolkit/flutter_ai_toolkit.dart';
import 'package:soliplex_client/controllers/app_state_controller.dart';

import 'package:soliplex_client/infrastructure/quick_agui/thread.dart';

class AguiProvider extends LlmProvider with ChangeNotifier {
  final Thread _thread;
  final String initialRunId;
  final String baseUrl;
  final String endpoint;
  final AppStateController appState;
  final List<String> chatVariables;

  static Future<AguiProvider> initialize({
    required ag_ui.AgUiClient client,
    required String baseUrl,
    required String endpoint,
    required AppStateController appState,
    required List<String> chatVariables,
    required Future<String?> Function() inquireInput,
  }) async {
    final httpClient = http.Client();
    debugPrint('body in initialize: ${jsonEncode({})}');
    final response = await httpClient.post(
      Uri.parse('$baseUrl/$endpoint/agui'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({}),
    );
    final jsonResponse = jsonDecode(response.body);
    debugPrint('response: $jsonResponse');
    debugPrint('runs: ${jsonResponse['runs'].keys}');

    return AguiProvider._(
      Thread(
        id: jsonResponse['thread_id'],
        client: client,
        tools: [
          ag_ui.Tool(
            name: 'query_position',
            description: 'query current device position',
            parameters: {},
          ),
        ],
        toolExecutors: {
          'query_position': (ag_ui.ToolCall call) async {
            debugPrint('call: ${call.toJsonString()}');
            final result = await inquireInput() ?? '';
            debugPrint('User entered: $result');
            return result;
          },
        },
      ),
      jsonResponse['runs'].keys.first,
      baseUrl,
      endpoint,
      appState,
      chatVariables,
    );
  }

  AguiProvider._(
    this._thread,
    this.initialRunId,
    this.baseUrl,
    this.endpoint,
    this.appState,
    this.chatVariables,
  );

  @override
  Iterable<ChatMessage> get history {
    return _thread.messageHistory
        .map(_toFlutterToolkitMessage)
        .where((msg) => msg.text?.isNotEmpty ?? false);
  }

  @override
  set history(Iterable<ChatMessage> newHistory) {
    debugPrint('WARN: Setting history is not supported in AguiThreadProvider');
    notifyListeners();
  }

  Future<String> _generateRunId() async {
    if (_thread.messageHistory.isEmpty) {
      debugPrint('returning initial run id');
      return initialRunId;
    }
    debugPrint('returning new run id');
    final client = http.Client();

    final response = await client.post(
      Uri.parse('$baseUrl/$endpoint/agui/${_thread.id}'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({}),
    );
    final jsonResponse = jsonDecode(response.body);
    debugPrint('json response for generate run id: $jsonResponse');
    debugPrint('returning run id: ${jsonResponse['run_id']}');
    return jsonResponse['run_id'];
  }

  String _generateAguiEndpoint({
    required String endpoint,
    required String threadId,
    required String runId,
  }) => '$endpoint/agui/$threadId/$runId';

  @override
  Stream<String> generateStream(
    String prompt, {
    Iterable<Attachment> attachments = const [],
  }) async* {
    debugPrint('generateStream called with: $prompt');

    String finalPrompt = prompt;
    for (var variable in chatVariables) {
      final stringVar = '\$$variable';
      if (prompt.contains(stringVar)) {
        try {
          final value = await appState.getVariable(variable);
          finalPrompt = prompt.replaceAll(stringVar, value);
        } catch (e) {
          debugPrint('Could not replace `$variable`. $e');
          finalPrompt = prompt;
        }
      }
    }

    final runId = await _generateRunId();

    final userMessage = ag_ui.UserMessage(
      id: '${_thread.id}_${runId}_user_message_id',
      content: finalPrompt,
    );

    debugPrint('initial run id: $runId');
    final toolCallsFuture = _thread.startRun(
      endpoint: _generateAguiEndpoint(
        endpoint: endpoint,
        threadId: _thread.id,
        runId: runId,
      ),
      runId: runId,
      messages: [userMessage],
    );

    final toolCalls = await toolCallsFuture;

    while (toolCalls.isNotEmpty) {
      final newRunId = await _generateRunId();
      debugPrint('new run id: $runId');
      final innerToolCallsFuture = _thread.startRun(
        endpoint: _generateAguiEndpoint(
          endpoint: endpoint,
          threadId: _thread.id,
          runId: newRunId,
        ),
        runId: newRunId,
        messages: toolCalls,
      );

      toolCalls.clear();
      final innerToolCalls = await innerToolCallsFuture;
      toolCalls.addAll(innerToolCalls);
    }

    // The framework handles event processing and emits messages via messageStream.
    // Our listener will call notifyListeners() which updates LlmChatView.
    // We yield empty here because the actual messages come through the listener.
    // This is a "push" model rather than the "pull" model that generateStream expects.
    yield '';
  }

  @override
  Stream<String> sendMessageStream(
    String prompt, {
    Iterable<Attachment> attachments = const [],
  }) {
    return generateStream(prompt, attachments: attachments);
  }

  ChatMessage _toFlutterToolkitMessage(ag_ui.Message message) {
    switch (message.role) {
      case ag_ui.MessageRole.developer:
      case ag_ui.MessageRole.system:
      case ag_ui.MessageRole.assistant:
        // Check if this is an AssistantMessage with toolCalls
        if (message is ag_ui.AssistantMessage &&
            message.toolCalls != null &&
            message.toolCalls!.isNotEmpty) {
          final toolCall = message.toolCalls!.first;

          // Special UI widget for approve_research_plan
          if (toolCall.function.name == 'approve_research_plan') {
            return ChatMessage(
              origin: MessageOrigin.llm,
              text: jsonEncode({
                'type': 'tool_call',
                'tool': toolCall.function.name,
                'toolCallId': toolCall.id,
              }),
              attachments: [],
            );
          }

          // For other tools, don't show in UI (server-side tools)
          return ChatMessage(
            origin: MessageOrigin.llm,
            text: '',
            attachments: [],
          );
        }

        // Regular assistant message with text content
        return ChatMessage(
          origin: MessageOrigin.llm,
          text: message.content ?? '',
          attachments: [],
        );

      case ag_ui.MessageRole.tool:
        // Don't show tool results in UI
        return ChatMessage(
          origin: MessageOrigin.llm,
          text: '',
          attachments: [],
        );

      case ag_ui.MessageRole.user:
        return ChatMessage(
          origin: MessageOrigin.user,
          text: message.content ?? '',
          attachments: [],
        );
    }
  }

  @override
  void dispose() {
    debugPrint('Disposing AguiThreadProvider');
    super.dispose();
  }
}
