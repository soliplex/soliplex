// Room-related models for the AG-UI Dashboard.
//
// These models represent the full room configuration data returned by the
// Soliplex API, including agent settings, tools, MCP toolsets, and more.

/// Configuration for a tool available in a room.
class RoomTool {
  const RoomTool({
    required this.id,
    required this.kind,
    required this.toolName,
    this.description,
    this.toolRequires = 'bare',
    this.allowMcp = true,
    this.extraParameters = const {},
  });

  factory RoomTool.fromJson(String id, Map<String, dynamic> json) {
    return RoomTool(
      id: id,
      kind: json['kind'] as String? ?? id,
      toolName: json['tool_name'] as String? ?? id,
      description: json['tool_description'] as String?,
      toolRequires: json['tool_requires'] as String? ?? 'bare',
      allowMcp: json['allow_mcp'] as bool? ?? true,
      extraParameters:
          (json['extra_parameters'] as Map<String, dynamic>?) ?? {},
    );
  }
  final String id;
  final String kind;
  final String toolName;
  final String? description;
  final String toolRequires; // 'fastapi_context', 'tool_config', 'bare'
  final bool allowMcp;
  final Map<String, dynamic> extraParameters;

  /// Check if this is a RAG-related tool.
  bool get isRagTool =>
      kind.contains('search') ||
      kind.contains('rag') ||
      extraParameters.containsKey('rag_lancedb_stem');

  @override
  String toString() => 'RoomTool($id: $kind)';
}

/// Agent configuration for a room.
class AgentConfig {
  const AgentConfig({
    required this.id,
    this.modelName,
    this.systemPrompt,
    this.providerType,
    this.providerBaseUrl,
    this.retries = 3,
    this.isFactory = false,
    this.factoryName,
    this.extraConfig,
  });

  factory AgentConfig.fromJson(Map<String, dynamic> json) {
    final isFactory = json.containsKey('factory_name');

    return AgentConfig(
      id: json['id'] as String? ?? 'unknown',
      modelName: json['model_name'] as String?,
      systemPrompt: json['system_prompt'] as String?,
      providerType: json['provider_type'] as String?,
      providerBaseUrl: json['provider_base_url'] as String?,
      retries: json['retries'] as int? ?? 3,
      isFactory: isFactory,
      factoryName: json['factory_name'] as String?,
      extraConfig: json['extra_config'] as Map<String, dynamic>?,
    );
  }
  final String id;
  final String? modelName;
  final String? systemPrompt;
  final String? providerType; // 'openai', 'ollama'
  final String? providerBaseUrl;
  final int retries;

  // Factory agent fields
  final bool isFactory;
  final String? factoryName;
  final Map<String, dynamic>? extraConfig;

  /// Get a display-friendly model name.
  String get displayModelName {
    if (isFactory) {
      return 'Factory: ${factoryName?.split('.').last ?? 'custom'}';
    }
    return modelName ?? 'Unknown';
  }

  /// Get the provider display name.
  String get displayProvider {
    if (isFactory) return 'Custom';
    switch (providerType) {
      case 'openai':
        return 'OpenAI';
      case 'ollama':
        return 'Ollama (Local)';
      default:
        return providerType ?? 'Unknown';
    }
  }

  @override
  String toString() => 'AgentConfig($id: $displayModelName)';
}

/// MCP (Model Context Protocol) toolset configuration.
class McpToolset {
  const McpToolset({
    required this.id,
    required this.kind,
    this.allowedTools,
    this.params = const {},
  });

  factory McpToolset.fromJson(String id, Map<String, dynamic> json) {
    final toolsetParams = json['toolset_params'] as Map<String, dynamic>? ?? {};
    List<String>? allowed;

    // allowed_tools can be in root or in toolset_params
    if (json['allowed_tools'] != null) {
      allowed = (json['allowed_tools'] as List).cast<String>();
    } else if (toolsetParams['allowed_tools'] != null) {
      allowed = (toolsetParams['allowed_tools'] as List).cast<String>();
    }

    return McpToolset(
      id: id,
      kind: json['kind'] as String? ?? 'unknown',
      allowedTools: allowed,
      params: toolsetParams,
    );
  }
  final String id;
  final String kind; // 'stdio', 'http'
  final List<String>? allowedTools;
  final Map<String, dynamic> params;

  /// Get the connection URL for HTTP toolsets.
  String? get url => kind == 'http' ? params['url'] as String? : null;

  /// Get the command for stdio toolsets.
  String? get command => kind == 'stdio' ? params['command'] as String? : null;

  @override
  String toString() => 'McpToolset($id: $kind)';
}

/// Full room configuration from the Soliplex API.
class Room {
  const Room({
    required this.id,
    required this.name,
    this.description,
    this.welcomeMessage,
    this.suggestions = const [],
    this.enableAttachments = false,
    this.allowMcp = false,
    this.agent,
    this.tools = const {},
    this.mcpClientToolsets = const {},
  });

  factory Room.fromJson(Map<String, dynamic> json) {
    // Parse tools
    final toolsJson = json['tools'] as Map<String, dynamic>? ?? {};
    final tools = <String, RoomTool>{};
    for (final entry in toolsJson.entries) {
      tools[entry.key] = RoomTool.fromJson(
        entry.key,
        entry.value as Map<String, dynamic>,
      );
    }

    // Parse MCP toolsets
    final mcpJson = json['mcp_client_toolsets'] as Map<String, dynamic>? ?? {};
    final mcpToolsets = <String, McpToolset>{};
    for (final entry in mcpJson.entries) {
      mcpToolsets[entry.key] = McpToolset.fromJson(
        entry.key,
        entry.value as Map<String, dynamic>,
      );
    }

    // Parse agent
    AgentConfig? agent;
    if (json['agent'] != null) {
      agent = AgentConfig.fromJson(json['agent'] as Map<String, dynamic>);
    }

    // Parse suggestions
    var suggestions = <String>[];
    if (json['suggestions'] != null) {
      suggestions = (json['suggestions'] as List).cast<String>();
    }

    return Room(
      id: json['id'] as String? ?? json['name'] as String,
      name: json['name'] as String? ?? json['id'] as String,
      description: json['description'] as String?,
      welcomeMessage: json['welcome_message'] as String?,
      suggestions: suggestions,
      enableAttachments: json['enable_attachments'] as bool? ?? false,
      allowMcp: json['allow_mcp'] as bool? ?? false,
      agent: agent,
      tools: tools,
      mcpClientToolsets: mcpToolsets,
    );
  }
  final String id;
  final String name;
  final String? description;
  final String? welcomeMessage;
  final List<String> suggestions;
  final bool enableAttachments;
  final bool allowMcp;

  final AgentConfig? agent;
  final Map<String, RoomTool> tools;
  final Map<String, McpToolset> mcpClientToolsets;

  /// Get the welcome message, falling back to description if not set.
  String? get effectiveWelcomeMessage => welcomeMessage ?? description;

  /// Check if this room has RAG capabilities.
  bool get hasRag => tools.values.any((t) => t.isRagTool);

  /// Check if this room has MCP integrations.
  bool get hasMcp => mcpClientToolsets.isNotEmpty;

  /// Get the total tool count.
  int get toolCount => tools.length;

  /// Get the total MCP toolset count.
  int get mcpToolsetCount => mcpClientToolsets.length;

  @override
  String toString() => 'Room($id: $name)';
}
