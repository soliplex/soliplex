import 'dart:async';
import 'dart:convert';

import 'package:equatable/equatable.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import 'package:soliplex/core/models/endpoint_models.dart';
import 'package:soliplex/core/network/network_inspector.dart';
import 'package:soliplex/core/utils/debug_log.dart';
import 'package:soliplex/core/utils/http_config.dart';

/// Result of probing a completions endpoint
class CompletionsProbeResult extends Equatable {
  const CompletionsProbeResult({
    required this.url,
    required this.isReachable,
    this.requiresApiKey = true,
    this.availableModels = const [],
    this.defaultModel,
    this.error,
  });

  /// Create a failed probe result
  factory CompletionsProbeResult.unreachable(String url, String error) {
    return CompletionsProbeResult(url: url, isReachable: false, error: error);
  }

  /// Create a successful probe result
  factory CompletionsProbeResult.success({
    required String url,
    required bool requiresApiKey,
    List<String> models = const [],
    String? defaultModel,
  }) {
    return CompletionsProbeResult(
      url: url,
      isReachable: true,
      requiresApiKey: requiresApiKey,
      availableModels: models,
      defaultModel: defaultModel ?? (models.isNotEmpty ? models.first : null),
    );
  }
  final String url;
  final bool isReachable;
  final bool requiresApiKey;
  final List<String> availableModels;
  final String? defaultModel;
  final String? error;

  /// Server is ready to use
  bool get isReady =>
      isReachable && (availableModels.isNotEmpty || defaultModel != null);

  /// Convert to CompletionsEndpoint type
  CompletionsEndpoint toEndpointType({String label = 'Completions Endpoint'}) {
    return CompletionsEndpoint(
      url: url,
      label: label,
      model: defaultModel ?? 'gpt-3.5-turbo',
      availableModels: availableModels.isNotEmpty ? availableModels : null,
      supportsModelDiscovery: availableModels.isNotEmpty,
    );
  }

  @override
  List<Object?> get props => [
    url,
    isReachable,
    requiresApiKey,
    availableModels,
    defaultModel,
    error,
  ];
}

/// Service for probing OpenAI-compatible completions endpoints
class CompletionsProbe {
  CompletionsProbe({http.Client? httpClient, NetworkInspector? inspector})
    : _httpClient = httpClient ?? http.Client(),
      _inspector = inspector;
  final http.Client _httpClient;
  final NetworkInspector? _inspector;

  /// Probe a completions endpoint to discover its capabilities.
  ///
  /// If [apiKey] is provided, uses it to authenticate the probe.
  /// Otherwise, probes without authentication (works for local endpoints like
  /// Ollama).
  Future<CompletionsProbeResult> probe(String url, {String? apiKey}) async {
    final normalizedUrl = _normalizeUrl(url);

    // Try to fetch /v1/models to discover available models
    final modelsResult = await _probeModelsEndpoint(
      normalizedUrl,
      apiKey: apiKey,
    );

    if (modelsResult != null) {
      return modelsResult;
    }

    // If /v1/models fails, try /v1/chat/completions with a minimal request
    // to verify the endpoint exists (without actually completing)
    return _probeChatEndpoint(normalizedUrl, apiKey: apiKey);
  }

  /// Normalize completions API URL
  String _normalizeUrl(String url) {
    var normalized = url.trim();

    // Remove trailing slash
    while (normalized.endsWith('/')) {
      normalized = normalized.substring(0, normalized.length - 1);
    }

    // Add https if no protocol
    if (!normalized.startsWith('http://') &&
        !normalized.startsWith('https://')) {
      // Default to https for remote, http for localhost
      if (normalized.contains('localhost') ||
          normalized.contains('127.0.0.1')) {
        normalized = 'http://$normalized';
      } else {
        normalized = 'https://$normalized';
      }
    }

    return normalized;
  }

  Future<CompletionsProbeResult?> _probeModelsEndpoint(
    String baseUrl, {
    String? apiKey,
  }) async {
    final modelsUrl = Uri.parse('$baseUrl/v1/models');
    final headers = _buildHeaders(apiKey);

    final requestId = _inspector?.recordRequest(
      method: 'GET',
      uri: modelsUrl,
      headers: headers,
    );

    try {
      final response = await _httpClient
          .get(modelsUrl, headers: headers)
          .timeout(HttpConfig.completionsProbeTimeout);

      _inspector?.recordResponse(
        requestId: requestId ?? '',
        statusCode: response.statusCode,
        headers: response.headers,
        body: response.body,
      );

      if (response.statusCode == 200) {
        final models = _parseModelsResponse(response.body);
        return CompletionsProbeResult.success(
          url: baseUrl,
          requiresApiKey: apiKey != null,
          models: models,
        );
      } else if (response.statusCode == 401) {
        // Endpoint exists but requires authentication
        return CompletionsProbeResult.success(
          url: baseUrl,
          requiresApiKey: true,
        );
      }
      // Other status codes - try chat endpoint
      return null;
    } on TimeoutException {
      _inspector?.recordError(
        requestId: requestId ?? '',
        error: 'Connection timed out',
      );
      return CompletionsProbeResult.unreachable(
        baseUrl,
        'Connection timed out',
      );
    } on Object catch (e) {
      _inspector?.recordError(requestId: requestId ?? '', error: e.toString());
      // Don't fail yet - try chat endpoint
      return null;
    }
  }

  Future<CompletionsProbeResult> _probeChatEndpoint(
    String baseUrl, {
    String? apiKey,
  }) async {
    // Just check if the endpoint responds to OPTIONS or a malformed POST
    // We don't want to actually send a chat request
    final chatUrl = Uri.parse('$baseUrl/v1/chat/completions');
    final headers = _buildHeaders(apiKey);

    final requestId = _inspector?.recordRequest(
      method: 'POST',
      uri: chatUrl,
      headers: headers,
    );

    try {
      // Send an empty body to see if endpoint exists
      // This should fail with 400/422 (bad request) if endpoint exists
      final response = await _httpClient
          .post(
            chatUrl,
            headers: {...headers, 'Content-Type': 'application/json'},
            body: '{}',
          )
          .timeout(HttpConfig.completionsProbeTimeout);

      _inspector?.recordResponse(
        requestId: requestId ?? '',
        statusCode: response.statusCode,
        headers: response.headers,
        body: response.body,
      );

      // If we get any response other than 404/network error, endpoint likely
      // exists
      if (response.statusCode == 401) {
        return CompletionsProbeResult.success(
          url: baseUrl,
          requiresApiKey: true,
        );
      } else if (response.statusCode == 400 ||
          response.statusCode == 422 ||
          response.statusCode == 200) {
        // Endpoint exists (400/422 = bad request but endpoint found, 200 =
        // weird but ok)
        return CompletionsProbeResult.success(
          url: baseUrl,
          requiresApiKey: apiKey != null,
        );
      } else if (response.statusCode == 404) {
        return CompletionsProbeResult.unreachable(
          baseUrl,
          'Completions endpoint not found at $baseUrl',
        );
      } else {
        return CompletionsProbeResult.unreachable(
          baseUrl,
          'Server returned status ${response.statusCode}',
        );
      }
    } on TimeoutException {
      _inspector?.recordError(
        requestId: requestId ?? '',
        error: 'Connection timed out',
      );
      return CompletionsProbeResult.unreachable(
        baseUrl,
        'Connection timed out',
      );
    } on Object catch (e) {
      _inspector?.recordError(requestId: requestId ?? '', error: e.toString());
      return CompletionsProbeResult.unreachable(baseUrl, e.toString());
    }
  }

  Map<String, String> _buildHeaders(String? apiKey) {
    if (apiKey == null || apiKey.isEmpty) {
      return const {};
    }
    return {'Authorization': 'Bearer $apiKey'};
  }

  List<String> _parseModelsResponse(String body) {
    try {
      final data = jsonDecode(body);
      if (data is Map<String, dynamic> && data['data'] is List) {
        final models = <String>[];
        final modelData = data['data'] as List<dynamic>;
        for (final model in modelData) {
          if (model is Map<String, dynamic> && model['id'] is String) {
            models.add(model['id'] as String);
          }
        }
        return models;
      }
    } on Object catch (e) {
      DebugLog.warn('CompletionsProbe: Failed to parse models response: $e');
    }
    return [];
  }

  void dispose() {
    _httpClient.close();
  }
}

// =============================================================================
// Provider
// =============================================================================

/// Provider for CompletionsProbe.
///
/// Creates a new probe instance. Note that this creates a new http.Client
/// each time - for heavy usage, consider caching the probe.
final completionsProbeProvider = Provider<CompletionsProbe>((ref) {
  final probe = CompletionsProbe();
  ref.onDispose(probe.dispose);
  return probe;
});
