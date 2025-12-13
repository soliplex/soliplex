import 'dart:async';
import 'dart:convert';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:http/http.dart' as http;

import '../utils/debug_log.dart';
import '../utils/url_builder.dart';
import 'cancel_token.dart';
import 'network_transport.dart';

/// HTTP-based network transport using ag_ui.AgUiClient.
///
/// Web-compatible implementation that wraps the ag_ui package.
/// Supports 401 retry with header refresh for token expiration.
class HttpTransport implements NetworkTransport {
  final String baseUrl;
  final http.Client _httpClient;
  final ag_ui.AgUiClient _agUiClient;
  Map<String, String>? _headers;
  final Future<Map<String, String>> Function()? _headerRefresher;
  final UrlBuilder _urlBuilder;

  HttpTransport({
    required this.baseUrl,
    http.Client? httpClient,
    Map<String, String>? defaultHeaders,
    Future<Map<String, String>> Function()? headerRefresher,
  })  : _httpClient = httpClient ?? http.Client(),
        _headers = defaultHeaders,
        _headerRefresher = headerRefresher,
        _urlBuilder = UrlBuilder(baseUrl),
        // Use serverUrl (not apiBaseUrl) because runEndpoint includes the api path.
        // The ag_ui client replaces the path instead of appending to it.
        _agUiClient = ag_ui.AgUiClient(
          config: ag_ui.AgUiClientConfig(baseUrl: UrlBuilder(baseUrl).serverUrl),
        );

  /// Current headers for requests.
  Map<String, String>? get defaultHeaders => _headers;

  @override
  Stream<ag_ui.BaseEvent> runAgent({
    required String endpoint,
    required ag_ui.RunAgentInput input,
    CancelToken? cancelToken,
  }) async* {
    cancelToken?.throwIfCancelled();

    // Create a broadcast controller to manage cancellation
    final controller = StreamController<ag_ui.BaseEvent>.broadcast();

    // Listen for cancellation
    StreamSubscription<void>? cancelSubscription;
    if (cancelToken != null) {
      cancelSubscription = cancelToken.onCancel.asStream().listen((_) {
        DebugLog.network('HttpTransport: Cancel requested, closing stream');
        controller.close();
      });
    }

    try {
      // Convert to SimpleRunAgentInput for the client
      final simpleInput = ag_ui.SimpleRunAgentInput(
        threadId: input.threadId,
        runId: input.runId,
        messages: input.messages,
        tools: input.tools,
        state: input.state,
      );
      final stream = _agUiClient.runAgent(endpoint, simpleInput);

      await for (final event in stream) {
        if (cancelToken?.isCancelled == true) {
          DebugLog.network('HttpTransport: Cancelled, stopping yield');
          break;
        }
        yield event;
      }
    } on CancelledException {
      DebugLog.network('HttpTransport: Stream cancelled');
      rethrow;
    } finally {
      await cancelSubscription?.cancel();
      await controller.close();
    }
  }

  @override
  Future<void> cancelRun({
    required String roomId,
    required String threadId,
    required String runId,
  }) async {
    // POST to cancel endpoint
    // Server may not support this - fail gracefully
    try {
      final uri = _urlBuilder.cancelRun(roomId, threadId, runId);
      var response = await _httpClient.post(
        uri,
        headers: {
          'Content-Type': 'application/json',
          ...?_headers,
        },
        body: '{}',
      );

      // 401 retry with header refresh
      if (response.statusCode == 401 && _headerRefresher != null) {
        DebugLog.network('HttpTransport: Cancel 401, refreshing headers...');
        _headers = await _headerRefresher!();
        response = await _httpClient.post(
          uri,
          headers: {
            'Content-Type': 'application/json',
            ...?_headers,
          },
          body: '{}',
        );
      }

      if (response.statusCode >= 400) {
        DebugLog.network('HttpTransport: Cancel request returned ${response.statusCode}');
      } else {
        DebugLog.network('HttpTransport: Cancel request successful');
      }
    } catch (e) {
      // Server cancel is optional - client-side cancel is the primary mechanism
      DebugLog.network('HttpTransport: Cancel request failed (non-critical): $e');
    }
  }

  @override
  Future<Map<String, dynamic>> post(
    Uri uri,
    Map<String, dynamic> body,
  ) async {
    var response = await _httpClient.post(
      uri,
      headers: {
        'Content-Type': 'application/json',
        ...?_headers,
      },
      body: jsonEncode(body),
    );

    // 401 retry with header refresh (single retry to avoid loops)
    if (response.statusCode == 401 && _headerRefresher != null) {
      DebugLog.network('HttpTransport: 401 received, refreshing headers...');
      _headers = await _headerRefresher!();
      response = await _httpClient.post(
        uri,
        headers: {
          'Content-Type': 'application/json',
          ...?_headers,
        },
        body: jsonEncode(body),
      );
      DebugLog.network('HttpTransport: Retry after refresh returned ${response.statusCode}');
    }

    if (response.statusCode >= 400) {
      throw HttpTransportException(
        'POST failed: ${response.statusCode} ${response.body}',
        response.statusCode,
      );
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  @override
  Future<void> close() async {
    _httpClient.close();
  }
}

/// Exception for HTTP transport errors.
class HttpTransportException implements Exception {
  final String message;
  final int statusCode;

  HttpTransportException(this.message, this.statusCode);

  @override
  String toString() => 'HttpTransportException: $message (status: $statusCode)';
}
