import 'dart:convert';

import 'package:http/http.dart' as http;

import 'package:soliplex_client/src/auth/oidc_auth_system.dart';
import 'package:soliplex_client/src/errors/exceptions.dart';

/// API client for pre-authentication endpoints.
///
/// Handles server probing and auth provider discovery before the user
/// is authenticated. Uses raw HTTP client since these endpoints don't
/// require authentication tokens.
class AuthApi {
  /// Creates an auth API client.
  AuthApi({required http.Client client}) : _client = client;

  final http.Client _client;

  /// Fetches available authentication providers from a server.
  ///
  /// Parameters:
  /// - [serverUrl]: The base server URL (e.g., 'https://api.example.com')
  ///
  /// Returns a list of [OIDCAuthSystem] providers available on the server.
  ///
  /// Throws:
  /// - [ApiException] if the server returns a non-200 status
  /// - [FormatException] if the response is not valid JSON
  Future<List<OIDCAuthSystem>> getAuthProviders(String serverUrl) async {
    final normalizedUrl = serverUrl.endsWith('/')
        ? serverUrl.substring(0, serverUrl.length - 1)
        : serverUrl;
    final uri = Uri.parse('$normalizedUrl/api/login');
    final response = await _client.get(uri);

    if (response.statusCode != 200) {
      throw ApiException(
        statusCode: response.statusCode,
        message: '$normalizedUrl returned ${response.statusCode}',
      );
    }

    final json = jsonDecode(response.body);
    if (json is! List) {
      throw const FormatException('Invalid response format');
    }

    return json
        .map((e) => OIDCAuthSystem.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
