import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/auth/web_auth_provider.dart';

/// Implementation of [WebAuthPendingStorage] using platform secure storage.
///
/// Persists auth state between browser redirect and OAuth callback for
/// web authentication flow. Uses the same [FlutterSecureStorage] backend as
/// token storage.
class SecurePendingStorage implements WebAuthPendingStorage {
  /// Creates a secure pending storage with the given [storage] instance.
  SecurePendingStorage({required FlutterSecureStorage storage})
      : _storage = storage;

  final FlutterSecureStorage _storage;

  static const _key = 'pending_auth_state';

  @override
  Future<void> savePendingAuth(String serverId, OIDCAuthSystem authSystem) {
    final json = jsonEncode({
      'serverId': serverId,
      'authSystem': authSystem.toJson(),
    });
    return _storage.write(key: _key, value: json);
  }

  @override
  Future<PendingAuthResult> getPendingAuth() async {
    final json = await _storage.read(key: _key);
    if (json == null) {
      return const NoPendingAuth();
    }

    try {
      final decoded = jsonDecode(json);
      if (decoded is! Map<String, dynamic>) {
        await _storage.delete(key: _key);
        return const NoPendingAuth();
      }

      final serverId = decoded['serverId'];
      final authSystemJson = decoded['authSystem'];

      if (serverId is! String || authSystemJson is! Map<String, dynamic>) {
        await _storage.delete(key: _key);
        return const NoPendingAuth();
      }

      // Validate required OIDCAuthSystem fields before parsing
      if (authSystemJson['id'] is! String ||
          authSystemJson['title'] is! String ||
          authSystemJson['server_url'] is! String ||
          authSystemJson['client_id'] is! String) {
        await _storage.delete(key: _key);
        return const NoPendingAuth();
      }

      final authSystem = OIDCAuthSystem.fromJson(authSystemJson);
      return PendingAuthFound(serverId: serverId, authSystem: authSystem);
    } on FormatException {
      // Malformed JSON - clear it
      await _storage.delete(key: _key);
      return const NoPendingAuth();
    }
  }

  @override
  Future<void> clearPendingAuth() => _storage.delete(key: _key);
}
