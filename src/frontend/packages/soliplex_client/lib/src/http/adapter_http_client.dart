import 'dart:async';

import 'package:http/http.dart' as http;
import 'package:soliplex_client/src/http/http_client_adapter.dart';

/// Bridges [HttpClientAdapter] to Dart's [http.Client] interface.
///
/// This allows injecting our HTTP stack (with platform-specific adapters and
/// observability) into libraries that accept `http.Client`, such as ag_ui's
/// `AgUiClient`.
///
/// The implementation detects SSE requests (Accept: text/event-stream) and
/// routes them through [HttpClientAdapter.requestStream]. Other requests use
/// [HttpClientAdapter.request] which provides proper status codes.
///
/// Example:
/// ```dart
/// final adapter = ObservableHttpAdapter(
///   adapter: createPlatformAdapter(),
///   observer: myObserver,
/// );
/// final httpClient = AdapterHttpClient(adapter: adapter);
///
/// // Use with AgUiClient
/// final agUiClient = AgUiClient(
///   config: config,
///   httpClient: httpClient,
/// );
/// ```
class AdapterHttpClient extends http.BaseClient {
  /// Creates an [AdapterHttpClient] that delegates to the given [adapter].
  AdapterHttpClient({required this.adapter});

  /// The underlying adapter that handles HTTP requests.
  final HttpClientAdapter adapter;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final bodyBytes = await _extractBody(request);
    final headers = Map<String, String>.from(request.headers);

    // Detect SSE requests by Accept header
    final acceptHeader = headers['accept'] ?? headers['Accept'] ?? '';
    final isStreamingRequest = acceptHeader.contains('text/event-stream');

    if (isStreamingRequest) {
      return _sendStreaming(request, headers, bodyBytes);
    } else {
      return _sendRegular(request, headers, bodyBytes);
    }
  }

  /// Handles SSE/streaming requests using [HttpClientAdapter.requestStream].
  Future<http.StreamedResponse> _sendStreaming(
    http.BaseRequest request,
    Map<String, String> headers,
    List<int>? bodyBytes,
  ) async {
    // Use requestStream for SSE - it throws NetworkException on HTTP errors
    final byteStream = adapter.requestStream(
      request.method,
      request.url,
      headers: headers,
      body: bodyBytes,
    );

    // requestStream throws on HTTP errors, so successful streams are 200
    return http.StreamedResponse(
      byteStream,
      200,
      request: request,
      headers: {'content-type': 'text/event-stream'},
    );
  }

  /// Handles regular requests using [HttpClientAdapter.request].
  Future<http.StreamedResponse> _sendRegular(
    http.BaseRequest request,
    Map<String, String> headers,
    List<int>? bodyBytes,
  ) async {
    final response = await adapter.request(
      request.method,
      request.url,
      headers: headers,
      body: bodyBytes,
    );

    // Convert AdapterResponse to StreamedResponse
    final bodyStream = Stream.value(response.bodyBytes);

    return http.StreamedResponse(
      bodyStream,
      response.statusCode,
      request: request,
      headers: response.headers,
      reasonPhrase: response.reasonPhrase,
      contentLength: response.bodyBytes.length,
    );
  }

  /// Extracts body bytes from the request.
  Future<List<int>?> _extractBody(http.BaseRequest request) async {
    if (request is http.Request) {
      final bodyBytes = request.bodyBytes;
      return bodyBytes.isNotEmpty ? bodyBytes : null;
    } else if (request is http.StreamedRequest) {
      final bytes = await request.finalize().toBytes();
      return bytes.isNotEmpty ? bytes : null;
    } else if (request is http.MultipartRequest) {
      final bytes = await request.finalize().toBytes();
      return bytes.isNotEmpty ? bytes : null;
    }
    return null;
  }

  @override
  void close() {
    adapter.close();
  }
}
