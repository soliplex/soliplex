import 'dart:async';

import 'package:meta/meta.dart';
import 'package:soliplex_client/src/models/chat_message.dart';

/// Function type for executing a tool call.
///
/// Takes a [ToolCallInfo] with the tool call details and returns a [Future]
/// that completes with the result string.
typedef ToolExecutor = Future<String> Function(ToolCallInfo call);

/// Information about a registered tool.
@immutable
class RegisteredTool {
  /// Creates a new [RegisteredTool] with the given configuration.
  const RegisteredTool({
    required this.name,
    required this.executor,
    this.fireAndForget = false,
    this.description,
  });

  /// The name of the tool.
  final String name;

  /// The function that executes the tool.
  final ToolExecutor executor;

  /// Whether the tool should be executed without waiting for results.
  ///
  /// Fire-and-forget tools are useful for side effects like logging
  /// or analytics that don't need to return results to the model.
  final bool fireAndForget;

  /// Optional description of what the tool does.
  final String? description;
}

/// Registry for client-side tool handlers.
///
/// Tools registered here will be executed when the AI model requests them.
/// Results are sent back to the model to continue the conversation.
///
/// Example:
/// ```dart
/// final registry = ToolRegistry();
///
/// // Register a tool
/// registry.register(
///   name: 'calculator',
///   executor: (call) async {
///     final args = jsonDecode(call.arguments ?? '{}');
///     final a = args['a'] as num;
///     final b = args['b'] as num;
///     return (a + b).toString();
///   },
///   description: 'Performs basic arithmetic operations',
/// );
///
/// // Execute a tool call
/// final result = await registry.execute(toolCallInfo);
/// ```
class ToolRegistry {
  final Map<String, RegisteredTool> _tools = {};

  /// Returns the number of registered tools.
  int get count => _tools.length;

  /// Returns the names of all registered tools.
  List<String> get registeredTools => _tools.keys.toList();

  /// Registers a tool handler.
  ///
  /// Throws [ArgumentError] if a tool with the same name is already registered.
  void register({
    required String name,
    required ToolExecutor executor,
    bool fireAndForget = false,
    String? description,
  }) {
    if (_tools.containsKey(name)) {
      throw ArgumentError(
        'Tool "$name" is already registered. '
        'Use unregister() first to replace it.',
      );
    }

    _tools[name] = RegisteredTool(
      name: name,
      executor: executor,
      fireAndForget: fireAndForget,
      description: description,
    );
  }

  /// Unregisters a tool by name.
  ///
  /// Returns true if the tool was found and removed, false otherwise.
  bool unregister(String name) {
    return _tools.remove(name) != null;
  }

  /// Checks if a tool is registered.
  bool isRegistered(String name) => _tools.containsKey(name);

  /// Checks if a tool is fire-and-forget.
  ///
  /// Returns false if the tool is not registered.
  bool isFireAndForget(String name) => _tools[name]?.fireAndForget ?? false;

  /// Gets information about a registered tool.
  ///
  /// Returns null if the tool is not registered.
  RegisteredTool? getToolInfo(String name) => _tools[name];

  /// Executes a tool call.
  ///
  /// Returns the result string if the tool is registered and completes
  /// successfully.
  ///
  /// Returns null if:
  /// - The tool is not registered
  /// - The tool is fire-and-forget (execution is started but not awaited)
  ///
  /// Throws any exception that the tool executor throws.
  Future<String?> execute(ToolCallInfo call) async {
    final tool = _tools[call.name];
    if (tool == null) {
      return null;
    }

    if (tool.fireAndForget) {
      // Start execution but don't wait for it
      unawaited(tool.executor(call));
      return null;
    }

    return tool.executor(call);
  }

  /// Executes a tool call, returning a default value if the tool is not found.
  ///
  /// Unlike [execute], this method:
  /// - Returns [defaultResult] instead of null when tool is not found
  /// - Still returns null for fire-and-forget tools
  Future<String?> executeOrDefault(
    ToolCallInfo call, {
    String defaultResult = 'Tool not found',
  }) async {
    final tool = _tools[call.name];
    if (tool == null) {
      return defaultResult;
    }

    if (tool.fireAndForget) {
      unawaited(tool.executor(call));
      return null;
    }

    return tool.executor(call);
  }

  /// Clears all registered tools.
  void clear() {
    _tools.clear();
  }
}
