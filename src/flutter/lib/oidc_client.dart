import 'dart:convert';

import 'package:flutter/foundation.dart';

import "package:http/http.dart" as http;

import 'oidc_auth_interactor.dart';

class OidcClient implements http.Client {
  final http.Client client;
  final OidcAuthInteractor middleware;
  final int maxRetries;

  OidcClient(this.client, this.middleware, {required this.maxRetries});

  @override
  void close() => client.close();

  @override
  Future<http.Response> delete(
    Uri url, {
    Map<String, String>? headers,
    Object? body,
    Encoding? encoding,
  }) async {
    final requestHeaders = headers ?? {};
    await middleware.applyToHeader(requestHeaders);
    return client.delete(
      url,
      headers: requestHeaders,
      body: body,
      encoding: encoding,
    );
  }

  @override
  Future<http.Response> get(Uri url, {Map<String, String>? headers}) async {
    return _retryRequest(url, headers: headers);
  }

  @override
  Future<http.Response> head(Uri url, {Map<String, String>? headers}) async {
    final requestHeaders = headers ?? {};
    await middleware.applyToHeader(requestHeaders);
    return client.head(url, headers: requestHeaders);
  }

  @override
  Future<http.Response> patch(
    Uri url, {
    Map<String, String>? headers,
    Object? body,
    Encoding? encoding,
  }) async {
    final requestHeaders = headers ?? {};
    await middleware.applyToHeader(requestHeaders);
    return client.patch(
      url,
      headers: requestHeaders,
      body: body,
      encoding: encoding,
    );
  }

  @override
  Future<http.Response> post(
    Uri url, {
    Map<String, String>? headers,
    Object? body,
    Encoding? encoding,
  }) async {
    final requestHeaders = headers ?? {};
    await middleware.applyToHeader(requestHeaders);
    return client.post(
      url,
      headers: requestHeaders,
      body: body,
      encoding: encoding,
    );
  }

  @override
  Future<http.Response> put(
    Uri url, {
    Map<String, String>? headers,
    Object? body,
    Encoding? encoding,
  }) async {
    final requestHeaders = headers ?? {};
    await middleware.applyToHeader(requestHeaders);
    return client.put(
      url,
      headers: requestHeaders,
      body: body,
      encoding: encoding,
    );
  }

  @override
  Future<String> read(Uri url, {Map<String, String>? headers}) async {
    final requestHeaders = headers ?? {};
    await middleware.applyToHeader(requestHeaders);
    return client.read(url, headers: requestHeaders);
  }

  @override
  Future<Uint8List> readBytes(Uri url, {Map<String, String>? headers}) async {
    final requestHeaders = headers ?? {};
    await middleware.applyToHeader(requestHeaders);
    return client.readBytes(url, headers: requestHeaders);
  }

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    await middleware.applyToRequest(request);
    return client.send(request);
  }

  Stream<T> postStream<T>({
    required String to,
    required T Function(Map<String, dynamic>) onSuccess,
    required String prompt,
  }) async* {
    try {
      final uri = Uri.parse(to);
      final headers = <String, String>{
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
      };
      final request = http.Request('POST', uri)
        ..headers.addAll(headers)
        ..followRedirects = true
        ..body = jsonEncode({'text': prompt});

      debugPrint("starting request to $to");

      try {
        final response = await send(request);

        try {
          debugPrint('Starting to consume stream response');
          final stream = response.stream
              .transform(utf8.decoder)
              .transform(const LineSplitter());

          try {
            final errorResponse = StringBuffer();
            await for (final value in stream.where(
              (event) => event.isNotEmpty,
            )) {
              final data = value;

              final dataLines = data
                  .split("\n")
                  .where((element) => element.isNotEmpty)
                  .toList();

              final decoded = jsonDecode(dataLines.last);
              yield onSuccess(decoded);
            } // end of await for
            if (errorResponse.isNotEmpty) {
              final decoded = jsonDecode(errorResponse.toString());
              if (decoded is List) {
                yield* Stream<T>.error(decoded.first as Map<String, dynamic>);
              } else {
                yield* Stream<T>.error(decoded as Map<String, dynamic>);
              }
              yield* Stream<T>.error(decoded);
            }
          } catch (error, stackTrace) {
            debugPrint('Error occurred while handling stream');
            yield* Stream<T>.error(
              error,
              stackTrace,
            ); // Error cases in handling stream
          }
        } catch (error, stackTrace) {
          debugPrint('Error occurred while decoding stream from response');
          yield* Stream<T>.error(
            error,
            stackTrace,
          ); // Error cases in decoding stream from response
        }
      } catch (e) {
        debugPrint('Error occurred while getting response from request');
        yield* Stream<T>.error(e); // Error cases in getting response
      }
    } catch (e) {
      debugPrint('Error occurred while making request');
      yield* Stream<T>.error(e); //Error cases in making request
    }
  }

  Future<http.Response> getWithTimeout(
    Uri url, {
    Duration? timeLimit,
    Map<String, String>? headers,
  }) async {
    if (timeLimit == null) {
      return get(url, headers: headers);
    }
    return _retryRequest(url, headers: headers, timeLimit: timeLimit);
  }

  Future<http.Response> postWithTimeout(
    Uri url, {
    Map<String, String>? headers,
    Object? body,
    Encoding? encoding,
    Duration? timeLimit,
  }) async {
    if (timeLimit == null) {
      return post(url, headers: headers, body: body, encoding: encoding);
    }
    final requestHeaders = headers ?? {};
    await middleware.applyToHeader(requestHeaders);
    return client
        .post(url, headers: requestHeaders, body: body, encoding: encoding)
        .timeout(timeLimit);
  }

  Future<http.Response> _retryRequest(
    Uri url, {
    Map<String, String>? headers,
    Duration? timeLimit,
  }) async {
    http.Response? failingResponse;
    for (int attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        final requestHeaders = headers ?? {};
        await middleware.applyToHeader(requestHeaders);
        final response = timeLimit == null
            ? await client.get(url, headers: requestHeaders)
            : await client.get(url, headers: requestHeaders).timeout(timeLimit);
        // Check if the response is successful (status code 200-299)
        if (response.statusCode >= 200 && response.statusCode < 300) {
          return response; // Return successful response
        }
        // Optionally, add handling for specific status codes to retry
        if (response.statusCode == 500 ||
            response.statusCode == 503 ||
            response.statusCode == 401) {
          failingResponse = response;
        } else {
          // For any other errors not handled, break out of the retry loop
          return response;
        }
      } catch (e) {
        // Handle specific exceptions if needed
        if (attempt == maxRetries - 1) {
          rethrow; // Re-throw on the last attempt
        }
      }
    }
    if (failingResponse != null) {
      return failingResponse;
    }
    throw Exception('Max retries exceeded.');
  }
}
