import 'package:meta/meta.dart';
import 'package:soliplex_client/src/auth/auth_result.dart';
import 'package:soliplex_client/src/auth/auth_token.dart';
import 'package:soliplex_client/src/auth/refresh_result.dart';
import 'package:soliplex_client/src/auth/token_result.dart';
import 'package:soliplex_client/src/auth/token_storage.dart';

/// Callback type for refreshing an expired token.
typedef RefreshCallback = Future<RefreshResult> Function(AuthToken token);

/// Validates and manages token lifecycle.
///
/// Encapsulates the shared token validation logic used by auth providers:
/// 1. Read token from storage
/// 2. Check if valid or needs refresh
/// 3. Attempt refresh if needed
/// 4. Persist updated token or clean up expired token
@immutable
class TokenValidator {
  /// Creates a token validator.
  const TokenValidator({required TokenStorage tokenStorage})
      : _tokenStorage = tokenStorage;

  final TokenStorage _tokenStorage;

  /// Gets a valid token for the given server.
  ///
  /// Returns:
  /// - [Authenticated] with valid token
  /// - [NoToken] if no token stored
  /// - [TokenExpired] if expired without refresh capability
  /// - [RefreshFailed] if refresh was attempted but rejected
  ///
  /// The [onRefresh] callback is invoked when a token needs refreshing.
  /// It should attempt to refresh the token and return the result.
  Future<AuthResult> getValidToken(
    String serverId, {
    required RefreshCallback onRefresh,
  }) async {
    final result = await _tokenStorage.read(serverId);

    switch (result) {
      case TokenNotFound():
        return const NoToken();
      case TokenStorageError(:final message):
        return StorageUnavailable(message: message);
      case TokenFound(:final token):
        if (!token.needsRefresh) {
          return Authenticated(token: token);
        }

        if (!token.canRefresh) {
          await _tokenStorage.delete(serverId);
          return const TokenExpired();
        }

        switch (await onRefresh(token)) {
          case RefreshSuccess(:final token):
            await _tokenStorage.write(serverId, token);
            return Authenticated(token: token);
          case RefreshRejected(:final cause):
            await _tokenStorage.delete(serverId);
            return RefreshFailed(cause: cause);
        }
    }
  }
}
