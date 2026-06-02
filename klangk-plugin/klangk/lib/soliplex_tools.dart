import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:klangk_plugin_api/klangk_plugin_api.dart';
import 'package:web/web.dart' as web;

/// localStorage key for the Soliplex access token.
const _tokenKey = 'soliplex_access_token';
const _refreshTokenKey = 'soliplex_refresh_token';
const _expiresAtKey = 'soliplex_expires_at';

/// Cached Soliplex URL fetched from the Klangk backend config.
String? _soliplexUrl;

/// Fetch the Soliplex URL from the Klangk backend config endpoint.
Future<String> _getSoliplexUrl() async {
  if (_soliplexUrl != null) return _soliplexUrl!;
  final resp = await http.get(Uri.parse('$baseUrl/api/config'));
  if (resp.statusCode == 200) {
    final data = jsonDecode(resp.body) as Map<String, dynamic>;
    _soliplexUrl = (data['soliplex_url'] as String? ?? '')
        .replaceAll(RegExp(r'/+$'), '');
  }
  _soliplexUrl ??= '';
  return _soliplexUrl!;
}

/// Get a valid access token, triggering OIDC login via popup if needed.
Future<String> _getAccessToken() async {
  // Check for a stored token that hasn't expired.
  final stored = web.window.localStorage.getItem(_tokenKey);
  final expiresAtStr = web.window.localStorage.getItem(_expiresAtKey);
  if (stored != null && stored.isNotEmpty && expiresAtStr != null) {
    final expiresAt = DateTime.tryParse(expiresAtStr);
    if (expiresAt != null &&
        expiresAt.isAfter(DateTime.now().add(Duration(seconds: 30)))) {
      return stored;
    }
  }

  // No valid token — trigger OIDC login via popup.
  final soliplexUrl = await _getSoliplexUrl();

  // Discover the first available auth system.
  final loginResp =
      await http.get(Uri.parse('$soliplexUrl/api/login'));
  if (loginResp.statusCode != 200) {
    throw Exception(
        'Failed to get auth systems: ${loginResp.statusCode}');
  }
  final systems =
      jsonDecode(loginResp.body) as Map<String, dynamic>;
  if (systems.isEmpty) {
    throw Exception('No OIDC auth systems configured on Soliplex');
  }
  // Prefer the 'pydio' (Enfold) auth system if available.
  final systemId = systems.containsKey('pydio')
      ? 'pydio'
      : systems.keys.first;

  // The Soliplex callback redirects to:
  //   {return_to}?token=XXX&refresh_token=YYY&expires_in=ZZZ
  //
  // We set return_to to a path on the same origin. There's no page
  // there, but we only need to read the URL query params from the
  // popup before the browser tries to render it.
  final callbackPath = '/soliplex-auth-callback';
  final loginUrl = '$soliplexUrl/api/login/$systemId'
      '?return_to=$callbackPath';

  // Open the popup.
  final popup = web.window.open(loginUrl, 'soliplex_auth',
      'width=500,height=600,popup=yes');

  // Poll the popup URL for the token query params. While the popup
  // is on the OIDC provider's domain, reading popup.location.href
  // throws (cross-origin). Once it redirects back to our origin,
  // we can read it.
  final completer = Completer<String>();

  final timer = Timer.periodic(Duration(milliseconds: 500), (t) {
    try {
      if (popup == null || popup.closed) {
        t.cancel();
        if (!completer.isCompleted) {
          completer.completeError(
              Exception('Auth popup was closed before completing'));
        }
        return;
      }
      final href = popup.location.href;
      if (href.contains('token=')) {
        t.cancel();
        popup.close();
        final uri = Uri.parse(href);
        final token = uri.queryParameters['token'];
        final refreshToken = uri.queryParameters['refresh_token'];
        final expiresIn = uri.queryParameters['expires_in'];
        if (token == null || token.isEmpty) {
          completer.completeError(
              Exception('No token in auth callback'));
          return;
        }
        // Store tokens.
        web.window.localStorage.setItem(_tokenKey, token);
        if (refreshToken != null) {
          web.window.localStorage.setItem(
              _refreshTokenKey, refreshToken);
        }
        if (expiresIn != null) {
          final expiry = DateTime.now()
              .add(Duration(seconds: int.parse(expiresIn)));
          web.window.localStorage.setItem(
              _expiresAtKey, expiry.toIso8601String());
        }
        completer.complete(token);
      }
    } catch (_) {
      // Cross-origin access to popup.location throws — keep polling.
    }
  });

  // Timeout after 2 minutes.
  Future.delayed(Duration(minutes: 2), () {
    if (!completer.isCompleted) {
      timer.cancel();
      try {
        popup?.close();
      } catch (_) {}
      completer.completeError(
          Exception('Auth popup timed out after 2 minutes'));
    }
  });

  return completer.future;
}

/// Lightweight Soliplex client that calls the Soliplex API directly.
class SoliplexClient {
  SoliplexClient();

  Future<Map<String, String>> _getHeaders() async {
    final headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    try {
      final token = await _getAccessToken();
      headers['Authorization'] = 'Bearer $token';
    } catch (_) {
      // Proceed without auth — server will return 401 if required.
    }
    return headers;
  }

  /// List all rooms the user has access to.
  Future<List<Map<String, dynamic>>> listRooms() async {
    final soliplexUrl = await _getSoliplexUrl();
    final headers = await _getHeaders();
    final response = await http.get(
      Uri.parse('$soliplexUrl/api/v1/rooms'),
      headers: headers,
    );
    if (response.statusCode != 200) {
      throw Exception(
          'Failed to list rooms: ${response.statusCode} ${response.body}');
    }
    final data = jsonDecode(response.body);
    if (data is Map) {
      return data.entries.map((e) {
        final room = e.value as Map<String, dynamic>;
        return {'room_id': e.key, ...room};
      }).toList();
    }
    if (data is List) {
      return data.cast<Map<String, dynamic>>();
    }
    return [];
  }

  /// Query a room by creating a thread, posting a question, and
  /// collecting the response.
  Future<String> queryRoom(String roomId, String question) async {
    final soliplexUrl = await _getSoliplexUrl();
    final headers = await _getHeaders();

    // 1. Create a new thread
    final threadResp = await http.post(
      Uri.parse('$soliplexUrl/api/v1/rooms/$roomId/agui'),
      headers: headers,
      body: jsonEncode({}),
    );
    if (threadResp.statusCode != 200) {
      throw Exception(
          'Failed to create thread: '
          '${threadResp.statusCode} ${threadResp.body}');
    }
    final threadData = jsonDecode(threadResp.body);
    final threadId = threadData['thread_id'] as String;

    final runs = threadData['runs'] as Map<String, dynamic>? ?? {};
    if (runs.isEmpty) {
      throw Exception('No run created for thread');
    }
    final runId = runs.keys.first;

    // 2. Post the question and collect the streamed SSE response
    final sseUrl =
        '$soliplexUrl/api/v1/rooms/$roomId/agui/$threadId/$runId';

    final runInput = jsonEncode({
      'thread_id': threadId,
      'run_id': runId,
      'state': null,
      'messages': [
        {
          'id': 'msg-${DateTime.now().millisecondsSinceEpoch}',
          'role': 'user',
          'content': question,
        }
      ],
      'tools': [],
      'context': [],
      'forwarded_props': null,
    });

    final client = http.Client();
    try {
      final request = http.Request('POST', Uri.parse(sseUrl));
      request.headers['Content-Type'] = 'application/json';
      request.headers['Accept'] = 'text/event-stream';
      try {
        final token = await _getAccessToken();
        request.headers['Authorization'] = 'Bearer $token';
      } catch (_) {}
      request.body = runInput;

      final streamedResp = await client.send(request);

      if (streamedResp.statusCode != 200) {
        final body = await streamedResp.stream.bytesToString();
        throw Exception(
            'Failed to run query: ${streamedResp.statusCode} $body');
      }

      final body = await streamedResp.stream.bytesToString();
      final responseText = _extractTextFromSseResponse(body);
      return responseText.isNotEmpty
          ? responseText
          : '(No response from Soliplex)';
    } finally {
      client.close();
    }
  }

  /// Parse SSE event stream and extract TEXT_MESSAGE_CONTENT deltas.
  String _extractTextFromSseResponse(String sseBody) {
    final buffer = StringBuffer();
    for (final line in sseBody.split('\n')) {
      if (!line.startsWith('data: ')) continue;
      final data = line.substring(6).trim();
      if (data.isEmpty || data == '[DONE]') continue;
      try {
        final event = jsonDecode(data) as Map<String, dynamic>;
        final type = event['type'] as String?;
        if (type == 'TEXT_MESSAGE_CONTENT') {
          buffer.write(event['delta'] ?? '');
        }
      } catch (_) {
        // Skip non-JSON lines
      }
    }
    return buffer.toString();
  }
}
