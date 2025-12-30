import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:soliplex_client/src/auth/auth_error.dart';
import 'package:soliplex_client/src/auth/auth_token.dart';
import 'package:soliplex_client/src/auth/sso_config.dart';
import 'package:soliplex_client/src/auth/token_result.dart';
import 'package:soliplex_client/src/auth/token_storage.dart';
import 'package:soliplex_client/src/auth/user_info.dart';

/// Fetches user information from an OIDC userinfo endpoint.
///
/// Shared implementation used by both mobile and web auth providers.
class UserInfoFetcher {
  /// Creates a user info fetcher.
  const UserInfoFetcher({
    required TokenStorage tokenStorage,
    required http.Client httpClient,
  })  : _tokenStorage = tokenStorage,
        _httpClient = httpClient;

  final TokenStorage _tokenStorage;
  final http.Client _httpClient;

  /// Fetches user info for the given server using stored credentials.
  ///
  /// Throws [AuthErrorNotAuthenticated] if no token is stored.
  /// Throws [AuthErrorConfiguration] if [config] has no userinfo endpoint.
  /// Throws [AuthErrorNetwork] on HTTP request failures.
  /// Throws [AuthErrorServer] on non-200 responses.
  Future<UserInfo> fetch(String serverId, SsoConfig config) async {
    final result = await _tokenStorage.read(serverId);

    final token = switch (result) {
      TokenFound(:final token) => token,
      TokenNotFound() => throw const AuthErrorNotAuthenticated(),
      TokenStorageError(:final message) => throw AuthErrorNetwork(
          message: 'Token storage access failed: $message',
        ),
    };

    return fetchWithToken(token, config);
  }

  /// Fetches user info using the provided token.
  ///
  /// Use this when you already have the token and don't need storage lookup.
  ///
  /// Throws [AuthErrorConfiguration] if [config] has no userinfo endpoint.
  /// Throws [AuthErrorNetwork] on HTTP request failures.
  /// Throws [AuthErrorServer] on non-200 responses.
  Future<UserInfo> fetchWithToken(AuthToken token, SsoConfig config) async {
    final userInfoEndpoint = config.userInfoEndpoint;
    if (userInfoEndpoint == null) {
      throw const AuthErrorConfiguration(
        message: 'No userinfo endpoint configured',
      );
    }

    final http.Response response;
    try {
      response = await _httpClient.get(
        Uri.parse(userInfoEndpoint),
        headers: {'Authorization': 'Bearer ${token.accessToken}'},
      );
    } on http.ClientException catch (e, st) {
      throw AuthErrorNetwork(
        message: 'Failed to fetch user info: $e',
        originalError: e,
        stackTrace: st,
      );
    }
    // No generic Exception catch: http.Client.get throws ClientException
    // for network failures. Any other exception indicates a bug.

    if (response.statusCode != 200) {
      throw AuthErrorServer(
        message: 'User info request failed',
        statusCode: response.statusCode,
        body: response.body,
      );
    }

    final json = jsonDecode(response.body) as Map<String, dynamic>;
    return UserInfo.fromOidcClaims(json);
  }
}
