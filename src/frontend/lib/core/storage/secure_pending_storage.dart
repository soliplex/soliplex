import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:soliplex_frontend/core/auth/web_auth_provider.dart';

/// Implementation of [WebAuthPendingStorage] using platform secure storage.
///
/// Persists the server ID between browser redirect and OAuth callback for
/// web authentication flow. Uses the same [FlutterSecureStorage] backend as
/// token storage.
class SecurePendingStorage implements WebAuthPendingStorage {
  /// Creates a secure pending storage with the given [storage] instance.
  SecurePendingStorage({required FlutterSecureStorage storage})
      : _storage = storage;

  final FlutterSecureStorage _storage;

  static const _key = 'pending_auth_server_id';

  @override
  Future<void> savePendingServerId(String serverId) async {
    await _storage.write(key: _key, value: serverId);
  }

  @override
  Future<PendingServerResult> getPendingServerId() async {
    final serverId = await _storage.read(key: _key);
    if (serverId == null) {
      return const NoPendingServer();
    }
    return PendingServerFound(serverId);
  }

  @override
  Future<void> clearPendingServerId() async {
    await _storage.delete(key: _key);
  }
}
