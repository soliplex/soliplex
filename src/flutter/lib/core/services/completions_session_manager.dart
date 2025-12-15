import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rxdart/rxdart.dart';
import 'package:soliplex/core/chat/chat_session.dart';
import 'package:soliplex/core/chat/completions_chat_session.dart';
import 'package:soliplex/core/chat/unified_message.dart';
import 'package:soliplex/core/models/chat_models.dart';
import 'package:soliplex/core/models/endpoint_models.dart';
import 'package:soliplex/core/models/saved_endpoint.dart';
import 'package:soliplex/core/network/network_transport_layer.dart';
import 'package:soliplex/core/services/secure_storage_service.dart';
import 'package:soliplex/core/utils/debug_log.dart';

/// State for tracking the active completions endpoint.
class CompletionsSessionState {
  const CompletionsSessionState({
    this.activeEndpoint,
    this.session,
    this.isLoading = false,
    this.error,
  });

  /// The currently active completions endpoint (null = using AG-UI mode).
  final SavedEndpoint? activeEndpoint;

  /// The active chat session (null if no endpoint selected).
  final ChatSession? session;

  /// Whether a session is currently being created.
  final bool isLoading;

  /// Error message if session creation failed.
  final String? error;

  /// Whether we're in completions mode (vs AG-UI mode).
  bool get isCompletionsMode => activeEndpoint != null;

  CompletionsSessionState copyWith({
    SavedEndpoint? activeEndpoint,
    ChatSession? session,
    bool? isLoading,
    String? error,
    bool clearEndpoint = false,
    bool clearSession = false,
    bool clearError = false,
  }) {
    return CompletionsSessionState(
      activeEndpoint: clearEndpoint
          ? null
          : (activeEndpoint ?? this.activeEndpoint),
      session: clearSession ? null : (session ?? this.session),
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

/// Manages completions chat sessions.
///
/// Handles creating and caching CompletionsChatSession instances
/// for selected endpoints.
class CompletionsSessionManager extends StateNotifier<CompletionsSessionState> {
  CompletionsSessionManager(this._storage)
    : super(const CompletionsSessionState());
  final SecureStorageService _storage;

  /// Select a completions endpoint and create a session.
  Future<void> selectEndpoint(SavedEndpoint endpoint) async {
    if (!endpoint.isCompletions) {
      DebugLog.warn('CompletionsSessionManager: Not a completions endpoint');
      return;
    }

    // If same endpoint already selected, do nothing
    if (state.activeEndpoint?.id == endpoint.id && state.session != null) {
      return;
    }

    // Dispose previous session
    await state.session?.dispose();

    state = state.copyWith(
      activeEndpoint: endpoint,
      isLoading: true,
      clearSession: true,
      clearError: true,
    );

    try {
      final config = endpoint.config as CompletionsEndpoint;

      // Get API key from secure storage
      final apiKey = await _storage.getApiKey(endpoint.id);

      // Create transport layer with API key
      final headers = <String, String>{};
      if (apiKey != null && apiKey.isNotEmpty) {
        headers['Authorization'] = 'Bearer $apiKey';
      }

      final transport = NetworkTransportLayer(
        baseUrl: config.url,
        defaultHeaders: headers,
      );

      // Create the session
      final session = CompletionsChatSession(
        transport: transport,
        model: config.model,
        endpointId: endpoint.id,
      );

      state = state.copyWith(session: session, isLoading: false);

      DebugLog.service(
        'CompletionsSessionManager: Created session for ${endpoint.name}',
      );
    } on Object catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: e.toString(),
        clearSession: true,
      );
      DebugLog.error('CompletionsSessionManager: Failed to create session: $e');
    }
  }

  /// Clear the active endpoint and return to AG-UI mode.
  Future<void> clearEndpoint() async {
    await state.session?.dispose();
    state = const CompletionsSessionState();
    DebugLog.service(
      'CompletionsSessionManager: Cleared endpoint, back to AG-UI mode',
    );
  }

  /// Send a message using the active completions session.
  Future<void> sendMessage(String content) async {
    final session = state.session;
    if (session == null) {
      throw StateError('No active completions session');
    }
    await session.sendMessage(content);
  }

  /// Clear the chat history.
  Future<void> clearHistory() async {
    await state.session?.clearHistory();
  }

  @override
  void dispose() {
    state.session?.dispose();
    super.dispose();
  }
}

// =============================================================================
// Providers
// =============================================================================

/// Provider for the completions session manager.
final completionsSessionManagerProvider =
    StateNotifierProvider<CompletionsSessionManager, CompletionsSessionState>((
      ref,
    ) {
      final storage = ref.watch(secureStorageProvider);
      return CompletionsSessionManager(storage);
    });

/// Whether we're currently in completions mode.
final isCompletionsModeProvider = Provider<bool>((ref) {
  return ref.watch(completionsSessionManagerProvider).isCompletionsMode;
});

/// The active completions endpoint (null if in AG-UI mode).
final activeCompletionsEndpointProvider = Provider<SavedEndpoint?>((ref) {
  return ref.watch(completionsSessionManagerProvider).activeEndpoint;
});

/// The active chat session (works for completions mode).
final activeCompletionsSessionProvider = Provider<ChatSession?>((ref) {
  return ref.watch(completionsSessionManagerProvider).session;
});

/// Stream of ChatMessage from the active completions session.
///
/// Converts UnifiedMessage to ChatMessage for UI compatibility.
final completionsMessageStreamProvider = StreamProvider<List<ChatMessage>>((
  ref,
) {
  final sessionState = ref.watch(completionsSessionManagerProvider);
  final session = sessionState.session;

  if (session == null) {
    return Stream.value(<ChatMessage>[]);
  }

  // Convert and stream messages
  return session.messageStream
      .startWith(session.messages)
      .map((messages) => messages.map(_unifiedToChatMessage).toList());
});

/// Convert a UnifiedMessage to a ChatMessage for the UI.
ChatMessage _unifiedToChatMessage(UnifiedMessage msg) {
  switch (msg) {
    case TextMessage(
      :final id,
      :final role,
      :final content,
      :final timestamp,
      :final isStreaming,
    ):
      return ChatMessage.text(
        id: id,
        user: role == MessageRole.user ? ChatUser.user : ChatUser.agent,
        text: content,
        createdAt: timestamp,
        isStreaming: isStreaming,
      );

    case ThinkingMessage(
      :final id,
      :final content,
      :final timestamp,
      :final isStreaming,
    ):
      // Show thinking as agent message with thinking fields
      return ChatMessage(
        id: id,
        user: ChatUser.agent,
        createdAt: timestamp,
        thinkingText: content,
        isThinkingStreaming: isStreaming,
      );

    case ToolCallMessage(
      :final id,
      :final toolName,
      :final timestamp,
      :final status,
    ):
      return ChatMessage.toolCall(
        id: id,
        user: ChatUser.agent,
        toolName: toolName,
        status: status.name,
        createdAt: timestamp,
      );

    case ToolResultMessage(:final id, :final timestamp):
      // Tool results are usually not displayed separately
      return ChatMessage(
        id: id,
        user: ChatUser.system,
        createdAt: timestamp,
        text: '[Tool result]',
      );

    case SystemMessage(:final id, :final content, :final timestamp):
      return ChatMessage.text(
        id: id,
        user: ChatUser.system,
        text: content,
        createdAt: timestamp,
      );

    case RichContentMessage(
      :final id,
      :final timestamp,
      :final contentType,
      :final payload,
    ):
      // For rich content, we'd need to handle this based on content type
      return ChatMessage(
        id: id,
        user: ChatUser.agent,
        createdAt: timestamp,
        text: '[$contentType content]',
        genUiContent: GenUiContent(
          toolCallId: id,
          widgetName: contentType,
          data: payload,
        ),
        type: MessageType.genUi,
      );
  }
}
