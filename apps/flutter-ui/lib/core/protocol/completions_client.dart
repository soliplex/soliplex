import 'dart:async';
import 'dart:convert';

import 'package:soliplex/core/network/network_transport_layer.dart'; // Import NetworkTransportLayer
import 'package:soliplex/core/protocol/completions_models.dart';
import 'package:soliplex/core/protocol/completions_stream_parser.dart';
import 'package:soliplex/core/utils/debug_log.dart';

class CompletionsClient {
  CompletionsClient({
    required this.baseUrl,
    required this.apiKey,
    required NetworkTransportLayer transportLayer, // Inject transport layer
  }) : _transportLayer = transportLayer,
       _parser = CompletionsStreamParser();
  final String baseUrl;
  final String apiKey;
  final NetworkTransportLayer _transportLayer; // Use NetworkTransportLayer
  final CompletionsStreamParser _parser;

  /// Send streaming chat completion request.
  Stream<CompletionChunk> streamComplete(CompletionRequest request) async* {
    // Ensure URL has /v1 prefix if not present (common for Ollama/LocalAI)
    var urlStr = baseUrl;
    if (urlStr.endsWith('/')) urlStr = urlStr.substring(0, urlStr.length - 1);

    if (!urlStr.endsWith('/v1')) {
      urlStr = '$urlStr/v1';
    }

    final url = Uri.parse('$urlStr/chat/completions');
    final headers = {if (apiKey.isNotEmpty) 'Authorization': 'Bearer $apiKey'};
    final body = jsonEncode(request.toJson());

    try {
      final stream = _transportLayer.streamPost(
        url,
        body,
        additionalHeaders: headers,
      );

      yield* _parser.parse(stream);
    } on Object catch (e) {
      DebugLog.error('CompletionsClient: Request failed: $e');
      rethrow;
    }
  }
}
