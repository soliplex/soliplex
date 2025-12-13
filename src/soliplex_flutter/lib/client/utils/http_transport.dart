import 'dart:convert';

import 'package:http/http.dart' as http;

/// HTTP transport layer for API requests.
class HttpTransport {
  HttpTransport({
    required this.baseUrl,
    this.defaultHeaders,
    this.timeout = const Duration(seconds: 30),
    http.Client? client,
  }) : _client = client ?? http.Client();

  final String baseUrl;
  final Map<String, String>? defaultHeaders;
  final Duration timeout;
  final http.Client _client;

  /// Make a GET request.
  Future<HttpResponse> get(Uri uri, {Map<String, String>? headers}) async {
    final response = await _client
        .get(uri, headers: _mergeHeaders(headers))
        .timeout(timeout);

    return HttpResponse(
      statusCode: response.statusCode,
      body: response.body,
      headers: response.headers,
    );
  }

  /// Make a POST request with JSON body.
  Future<HttpResponse> post(
    Uri uri, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
  }) async {
    final response = await _client
        .post(
          uri,
          headers: _mergeHeaders(headers, contentType: 'application/json'),
          body: body != null ? jsonEncode(body) : null,
        )
        .timeout(timeout);

    return HttpResponse(
      statusCode: response.statusCode,
      body: response.body,
      headers: response.headers,
    );
  }

  /// Make a DELETE request.
  Future<HttpResponse> delete(Uri uri, {Map<String, String>? headers}) async {
    final response = await _client
        .delete(uri, headers: _mergeHeaders(headers))
        .timeout(timeout);

    return HttpResponse(
      statusCode: response.statusCode,
      body: response.body,
      headers: response.headers,
    );
  }

  Map<String, String> _mergeHeaders(
    Map<String, String>? headers, {
    String? contentType,
  }) {
    return {
      if (defaultHeaders != null) ...defaultHeaders!,
      if (contentType != null) 'Content-Type': contentType,
      if (headers != null) ...headers,
    };
  }

  /// Close the client.
  void close() {
    _client.close();
  }
}

/// HTTP response wrapper.
class HttpResponse {
  const HttpResponse({
    required this.statusCode,
    required this.body,
    required this.headers,
  });

  final int statusCode;
  final String body;
  final Map<String, String> headers;

  /// Whether the request was successful (2xx).
  bool get isSuccess => statusCode >= 200 && statusCode < 300;

  /// Parse body as JSON.
  dynamic get json => jsonDecode(body);

  /// Parse body as JSON map.
  Map<String, dynamic> get jsonMap => json as Map<String, dynamic>;

  /// Parse body as JSON list.
  List<dynamic> get jsonList => json as List<dynamic>;

  @override
  String toString() => 'HttpResponse(statusCode: $statusCode)';
}

/// Exception for HTTP errors.
class HttpException implements Exception {
  const HttpException({
    required this.statusCode,
    required this.body,
    this.message,
  });

  final int statusCode;
  final String body;
  final String? message;

  @override
  String toString() {
    if (message != null) {
      return 'HttpException($statusCode): $message';
    }
    return 'HttpException($statusCode): $body';
  }
}
