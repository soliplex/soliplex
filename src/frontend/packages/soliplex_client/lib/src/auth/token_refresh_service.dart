import 'dart:convert';

import 'package:soliplex_client/src/errors/exceptions.dart';
import 'package:soliplex_client/src/http/http_response.dart';
import 'package:soliplex_client/src/http/soliplex_http_client.dart';

/// Result of a token refresh operation.
sealed class TokenRefreshResult {
  const TokenRefreshResult();
}

/// Successful token refresh.
class TokenRefreshSuccess extends TokenRefreshResult {
  /// Creates a successful token refresh result.
  const TokenRefreshSuccess({
    required this.accessToken,
    required this.refreshToken,
    required this.expiresAt,
    this.idToken,
  });

  /// The new access token.
  final String accessToken;

  /// The refresh token (new if rotated, original otherwise).
  final String refreshToken;

  /// When the access token expires.
  final DateTime expiresAt;

  /// New ID token if returned by IdP, null otherwise.
  ///
  /// Per OIDC Core 1.0 Section 12.2, refresh token responses "might not
  /// contain an id_token." Whether an IdP returns a new id_token depends on
  /// implementation, requested scopes, and provider policies.
  ///
  /// Callers should preserve the existing id_token when this is null:
  /// ```dart
  /// final idToken = result.idToken ?? currentState.idToken;
  /// ```
  final String? idToken;
}

/// Failed token refresh.
class TokenRefreshFailure extends TokenRefreshResult {
  /// Creates a failed token refresh result.
  const TokenRefreshFailure(this.reason);

  /// The reason for failure.
  final TokenRefreshFailureReason reason;
}

/// Reason for token refresh failure.
enum TokenRefreshFailureReason {
  /// No refresh token provided.
  ///
  /// Not an error condition - some auth flows don't issue refresh tokens.
  /// Caller should continue with current token until it expires.
  noRefreshToken,

  /// Refresh token rejected by IdP (expired, revoked, or already used).
  ///
  /// User must re-authenticate.
  invalidGrant,

  /// Network error during refresh.
  ///
  /// Retry may succeed.
  networkError,

  /// Unexpected error during refresh.
  unknownError,
}

/// Service for refreshing OAuth tokens.
///
/// Pure Dart class with explicit dependencies for easy testing.
/// Handles OIDC discovery and token refresh HTTP calls.
class TokenRefreshService {
  /// Creates a token refresh service.
  ///
  /// [httpClient] is used for all HTTP calls (discovery + refresh).
  /// Use a non-authenticated client to avoid circular dependencies.
  ///
  /// [onDiagnostic] receives debug messages. Defaults to no-op.
  TokenRefreshService({
    required SoliplexHttpClient httpClient,
    void Function(String) onDiagnostic = _noOp,
  })  : _httpClient = httpClient,
        _onDiagnostic = onDiagnostic;

  final SoliplexHttpClient _httpClient;
  final void Function(String) _onDiagnostic;

  static void _noOp(String _) {}

  /// Fallback token lifetime when IdP doesn't return expires_in.
  static const fallbackTokenLifetime = Duration(minutes: 30);

  /// How long before expiry to trigger proactive refresh.
  static const refreshThreshold = Duration(minutes: 1);

  /// Attempt to refresh tokens.
  ///
  /// Fetches the OIDC discovery document to find the token endpoint,
  /// then POSTs a refresh_token grant.
  ///
  /// Returns [TokenRefreshFailure] with
  /// [TokenRefreshFailureReason.noRefreshToken] if [refreshToken] is empty.
  Future<TokenRefreshResult> refresh({
    required String discoveryUrl,
    required String refreshToken,
    required String clientId,
  }) async {
    if (refreshToken.isEmpty) {
      return const TokenRefreshFailure(
        TokenRefreshFailureReason.noRefreshToken,
      );
    }

    try {
      final discoveryUri = Uri.parse(discoveryUrl);
      final tokenUri = await _fetchTokenEndpoint(discoveryUri);

      final tokenResponse = await _postRefreshGrant(
        tokenUri: tokenUri,
        refreshToken: refreshToken,
        clientId: clientId,
      );

      return _parseTokenResponse(tokenResponse, refreshToken);
    } on NetworkException {
      return const TokenRefreshFailure(TokenRefreshFailureReason.networkError);
    } on _DiscoveryException catch (e) {
      _onDiagnostic('TokenRefreshService: ${e.message}');
      return const TokenRefreshFailure(TokenRefreshFailureReason.unknownError);
    } catch (_) {
      return const TokenRefreshFailure(TokenRefreshFailureReason.unknownError);
    }
  }

  /// Fetch the token endpoint from OIDC discovery document.
  Future<Uri> _fetchTokenEndpoint(Uri discoveryUrl) async {
    final HttpResponse response;
    try {
      response = await _httpClient.request(
        'GET',
        discoveryUrl,
        timeout: const Duration(seconds: 10),
      );
    } on Exception catch (e) {
      throw NetworkException(
        message: 'Failed to fetch OIDC configuration',
        originalError: e,
      );
    }

    if (response.statusCode != 200) {
      throw _DiscoveryException(
        'OIDC discovery failed: ${response.statusCode}',
      );
    }

    final Map<String, dynamic> discovery;
    try {
      discovery = jsonDecode(response.body) as Map<String, dynamic>;
    } on FormatException {
      throw _DiscoveryException('Invalid OIDC discovery document');
    }

    final tokenEndpoint = discovery['token_endpoint'] as String?;
    if (tokenEndpoint == null) {
      throw _DiscoveryException('OIDC discovery missing token_endpoint');
    }

    final tokenUri = Uri.parse(tokenEndpoint);

    // Validate token endpoint origin matches discovery origin (SSRF prevention)
    if (tokenUri.host != discoveryUrl.host ||
        tokenUri.scheme != discoveryUrl.scheme ||
        tokenUri.port != discoveryUrl.port) {
      throw _DiscoveryException(
        'Token endpoint origin mismatch: expected '
        '${discoveryUrl.origin}, got ${tokenUri.origin}',
      );
    }

    return tokenUri;
  }

  /// POST refresh_token grant to token endpoint.
  Future<HttpResponse> _postRefreshGrant({
    required Uri tokenUri,
    required String refreshToken,
    required String clientId,
  }) async {
    try {
      return await _httpClient.request(
        'POST',
        tokenUri,
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: Uri(
          queryParameters: {
            'grant_type': 'refresh_token',
            'refresh_token': refreshToken,
            'client_id': clientId,
          },
        ).query,
        timeout: const Duration(seconds: 30),
      );
    } on Exception catch (e) {
      throw NetworkException(
        message: 'Token refresh request failed',
        originalError: e,
      );
    }
  }

  /// Parse token endpoint response.
  TokenRefreshResult _parseTokenResponse(
    HttpResponse response,
    String originalRefreshToken,
  ) {
    final Map<String, dynamic> tokenData;
    try {
      tokenData = jsonDecode(response.body) as Map<String, dynamic>;
    } on FormatException {
      return const TokenRefreshFailure(TokenRefreshFailureReason.unknownError);
    }

    // Handle error responses
    if (response.statusCode != 200) {
      final error = tokenData['error'] as String?;
      if (error == 'invalid_grant') {
        return const TokenRefreshFailure(
          TokenRefreshFailureReason.invalidGrant,
        );
      }
      return const TokenRefreshFailure(TokenRefreshFailureReason.unknownError);
    }

    // Parse successful response
    final accessToken = tokenData['access_token'] as String?;
    if (accessToken == null) {
      return const TokenRefreshFailure(TokenRefreshFailureReason.unknownError);
    }

    DateTime expiresAt;
    final expiresIn = tokenData['expires_in'] as int?;
    if (expiresIn != null) {
      expiresAt = DateTime.now().add(Duration(seconds: expiresIn));
    } else {
      expiresAt = DateTime.now().add(fallbackTokenLifetime);
    }

    final newRefreshToken =
        tokenData['refresh_token'] as String? ?? originalRefreshToken;

    return TokenRefreshSuccess(
      accessToken: accessToken,
      refreshToken: newRefreshToken,
      expiresAt: expiresAt,
      idToken: tokenData['id_token'] as String?,
    );
  }
}

/// Internal exception for discovery failures.
class _DiscoveryException implements Exception {
  _DiscoveryException(this.message);
  final String message;
}
