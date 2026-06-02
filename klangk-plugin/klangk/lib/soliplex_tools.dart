import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:klangk_plugin_api/klangk_plugin_api.dart';
import 'package:web/web.dart' as web;

/// localStorage keys for the Soliplex auth state.
const _tokenKey = 'soliplex_access_token';
const _refreshTokenKey = 'soliplex_refresh_token';
const _expiresAtKey = 'soliplex_expires_at';
const _serverUrlKey = 'soliplex_server_url';
const _clientIdKey = 'soliplex_client_id';

/// Cached Soliplex URL fetched from the Klangk backend config.
String? _soliplexUrl;

/// Cached OIDC token endpoint from discovery.
String? _tokenEndpoint;

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

/// Discover the OIDC token endpoint from the server_url.
Future<String?> _getTokenEndpoint(String serverUrl) async {
  if (_tokenEndpoint != null) return _tokenEndpoint;
  final url = serverUrl.replaceAll(RegExp(r'/+$'), '');
  final resp = await http.get(
      Uri.parse('$url/.well-known/openid-configuration'));
  if (resp.statusCode == 200) {
    final data = jsonDecode(resp.body) as Map<String, dynamic>;
    _tokenEndpoint = data['token_endpoint'] as String?;
  }
  return _tokenEndpoint;
}

/// Try to refresh the access token using the stored refresh token.
/// Returns the new access token, or null if refresh failed.
Future<String?> _tryRefreshToken() async {
  final refreshToken =
      web.window.localStorage.getItem(_refreshTokenKey);
  final serverUrl = web.window.localStorage.getItem(_serverUrlKey);
  final clientId = web.window.localStorage.getItem(_clientIdKey);
  if (refreshToken == null || serverUrl == null || clientId == null) {
    return null;
  }

  final tokenEndpoint = await _getTokenEndpoint(serverUrl);
  if (tokenEndpoint == null) return null;

  final resp = await http.post(
    Uri.parse(tokenEndpoint),
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: {
      'grant_type': 'refresh_token',
      'refresh_token': refreshToken,
      'client_id': clientId,
    },
  );

  if (resp.statusCode != 200) return null;

  final data = jsonDecode(resp.body) as Map<String, dynamic>;
  final newToken = data['access_token'] as String?;
  final newRefresh = data['refresh_token'] as String?;
  final expiresIn = data['expires_in'] as int?;

  if (newToken == null) return null;

  web.window.localStorage.setItem(_tokenKey, newToken);
  if (newRefresh != null) {
    web.window.localStorage.setItem(_refreshTokenKey, newRefresh);
  }
  if (expiresIn != null) {
    final expiry =
        DateTime.now().add(Duration(seconds: expiresIn));
    web.window.localStorage.setItem(
        _expiresAtKey, expiry.toIso8601String());
  }
  return newToken;
}

/// Check whether we have a valid (non-expired) access token.
bool hasValidToken() {
  final stored = web.window.localStorage.getItem(_tokenKey);
  final expiresAtStr = web.window.localStorage.getItem(_expiresAtKey);
  if (stored == null || stored.isEmpty || expiresAtStr == null) {
    return false;
  }
  final expiresAt = DateTime.tryParse(expiresAtStr);
  return expiresAt != null &&
      expiresAt.isAfter(DateTime.now().add(Duration(seconds: 30)));
}

/// Get a valid access token. Tries in order:
/// 1. Cached token if not expired
/// 2. Silent refresh using refresh_token
/// Throws if neither works (caller should direct user to log in
/// via the overlay button).
Future<String> _getAccessToken() async {
  // 1. Check for a stored token that hasn't expired.
  final stored = web.window.localStorage.getItem(_tokenKey);
  final expiresAtStr = web.window.localStorage.getItem(_expiresAtKey);
  if (stored != null && stored.isNotEmpty && expiresAtStr != null) {
    final expiresAt = DateTime.tryParse(expiresAtStr);
    if (expiresAt != null &&
        expiresAt.isAfter(DateTime.now().add(Duration(seconds: 30)))) {
      return stored;
    }
  }

  // 2. Try silent refresh.
  final refreshed = await _tryRefreshToken();
  if (refreshed != null) return refreshed;

  // 3. No valid token and refresh failed.
  throw Exception(
      'Not authenticated. Click "Connect to Soliplex" to log in.');
}

/// Perform OIDC login via a browser popup. Must be called from a
/// user gesture (e.g., button click) to avoid popup blockers.
/// Stores the access token, refresh token, expiry, server URL,
/// and client ID in localStorage.
Future<String> popupLogin() async {
  final soliplexUrl = await _getSoliplexUrl();

  // Discover available auth systems.
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

  // Store the server_url and client_id for future token refreshes.
  final systemData = systems[systemId] as Map<String, dynamic>;
  final serverUrl = systemData['server_url'] as String?;
  final clientId = systemData['client_id'] as String?;
  if (serverUrl != null) {
    web.window.localStorage.setItem(_serverUrlKey, serverUrl);
  }
  if (clientId != null) {
    web.window.localStorage.setItem(_clientIdKey, clientId);
  }

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
