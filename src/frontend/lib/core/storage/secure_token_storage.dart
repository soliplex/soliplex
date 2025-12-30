import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:soliplex_client/soliplex_client.dart';

/// Implementation of [TokenStorage] using platform secure storage.
///
/// Uses flutter_secure_storage which provides:
/// - iOS: Keychain
/// - Android: EncryptedSharedPreferences
/// - Web: localStorage (not truly secure - see note below)
/// - macOS: Keychain
/// - Linux: libsecret
/// - Windows: Windows Credentials API
///
/// **Web Security Note**: On web, tokens are stored in localStorage which is
/// accessible to JavaScript. This is acceptable for typical web apps where
/// the main threat model is XSS (and if you have XSS, you're compromised
/// regardless of where tokens are stored). For higher security requirements,
/// consider httpOnly cookies via backend-mediated auth.
class SecureTokenStorage implements TokenStorage {
  /// Creates a secure token storage with the given [storage] instance.
  ///
  /// The [keyPrefix] is prepended to all storage keys to namespace tokens.
  /// Defaults to 'auth_token_'.
  SecureTokenStorage({
    required FlutterSecureStorage storage,
    this.keyPrefix = 'auth_token_',
  }) : _storage = storage;

  final FlutterSecureStorage _storage;

  /// Prefix for storage keys.
  final String keyPrefix;

  String _keyFor(String serverId) => '$keyPrefix$serverId';

  @override
  Future<TokenResult> read(String serverId) async {
    final key = _keyFor(serverId);

    // Platform storage access - failures here are not "no token"
    final String? json;
    try {
      json = await _storage.read(key: key);
    } on Exception catch (e) {
      return TokenStorageError(
        message: 'Failed to access secure storage: $e',
        originalError: e,
      );
    }

    if (json == null) {
      return const TokenNotFound();
    }

    // Parse stored JSON - failures here are corruption, not access errors
    try {
      final decoded = jsonDecode(json);
      if (decoded is! Map<String, dynamic>) {
        await _storage.delete(key: key);
        return const TokenNotFound();
      }
      final token = AuthToken.fromJson(decoded);
      return TokenFound(token);
      // ignore: avoid_catches_without_on_clauses
    } catch (_) {
      // Corrupted data - delete and treat as not found
      await _storage.delete(key: key);
      return const TokenNotFound();
    }
  }

  @override
  Future<void> write(String serverId, AuthToken token) async {
    final key = _keyFor(serverId);
    final json = jsonEncode(token.toJson());
    await _storage.write(key: key, value: json);
  }

  @override
  Future<void> delete(String serverId) async {
    final key = _keyFor(serverId);
    await _storage.delete(key: key);
  }
}
