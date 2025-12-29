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
    final json = await _storage.read(key: key);

    if (json == null) {
      return const TokenNotFound();
    }

    final data = jsonDecode(json) as Map<String, dynamic>;
    final token = AuthToken.fromJson(data);
    return TokenFound(token);
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
