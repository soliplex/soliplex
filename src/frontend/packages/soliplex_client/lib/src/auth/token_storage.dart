import 'package:soliplex_client/src/auth/auth_token.dart';
import 'package:soliplex_client/src/auth/token_result.dart';

/// Storage interface for authentication tokens.
///
/// Implementations handle platform-specific secure storage
/// (e.g., flutter_secure_storage for mobile, web storage for browser).
///
/// Each server is identified by a unique `serverId` string (typically the
/// server URL or a derived stable identifier), allowing multiple server
/// connections to be stored independently.
abstract interface class TokenStorage {
  /// Reads the stored token for `serverId`.
  ///
  /// Returns [TokenFound] with the token if one is stored.
  /// Returns [TokenNotFound] if no token exists for this server.
  /// Throws on storage access failures (e.g., keychain unavailable,
  /// permissions denied, corrupted data).
  Future<TokenResult> read(String serverId);

  /// Writes `token` for `serverId`.
  ///
  /// Overwrites any existing token for this server.
  /// Throws on storage access failures.
  Future<void> write(String serverId, AuthToken token);

  /// Deletes the token for `serverId`.
  ///
  /// This operation is idempotent - calling delete on a non-existent
  /// key does not throw an error.
  /// Throws on storage access failures.
  Future<void> delete(String serverId);
}
