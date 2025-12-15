import 'package:soliplex/core/auth/secure_storage_gateway.dart';
import 'package:soliplex/core/auth/sso_config.dart';

/// Storage for SSO configurations, scoped by server ID.
///
/// Each server has its own SSO config to prevent state pollution
/// when switching between multiple OIDC-authenticated servers.
class SecureSsoStorage {
  SecureSsoStorage(this._storage);
  final SecureStorageGateway _storage;

  /// Get storage key scoped to a specific server.
  String _key(String serverId, String field) => 'sso.$serverId.$field';

  /// Store SSO config for a specific server.
  Future<void> setSsoConfig(String serverId, SsoConfig config) async {
    await _storage.write(_key(serverId, 'id'), config.id);
    await _storage.write(_key(serverId, 'title'), config.title);
    await _storage.write(_key(serverId, 'endpoint'), config.endpoint);
    await _storage.write(_key(serverId, 'tokenEndpoint'), config.tokenEndpoint);
    await _storage.write(
      _key(serverId, 'loginUri'),
      config.loginUrl.toString(),
    );
    await _storage.write(_key(serverId, 'clientId'), config.clientId);
    await _storage.write(_key(serverId, 'redirectUrl'), config.redirectUrl);
    await _storage.write(_key(serverId, 'scopes'), config.scopes.join(','));
  }

  /// Retrieve SSO config for a specific server.
  Future<SsoConfig?> getSsoConfig(String serverId) async {
    final id = await _storage.read(_key(serverId, 'id'));
    final title = await _storage.read(_key(serverId, 'title'));
    final endpoint = await _storage.read(_key(serverId, 'endpoint'));
    final tokenEndpoint = await _storage.read(_key(serverId, 'tokenEndpoint'));
    final loginUri = await _storage.read(_key(serverId, 'loginUri'));
    final clientId = await _storage.read(_key(serverId, 'clientId'));
    final redirectUrl = await _storage.read(_key(serverId, 'redirectUrl'));
    final scopes = await _storage.read(_key(serverId, 'scopes'));

    if (id == null ||
        title == null ||
        endpoint == null ||
        tokenEndpoint == null ||
        loginUri == null ||
        clientId == null ||
        redirectUrl == null ||
        scopes == null) {
      return null;
    }

    return SsoConfig(
      id: id,
      title: title,
      endpoint: endpoint,
      tokenEndpoint: tokenEndpoint,
      loginUrl: Uri.parse(loginUri),
      clientId: clientId,
      redirectUrl: redirectUrl,
      scopes: scopes.split(','),
    );
  }

  /// Delete SSO config for a specific server.
  Future<void> deleteSsoConfig(String serverId) async {
    await _storage.delete(_key(serverId, 'id'));
    await _storage.delete(_key(serverId, 'title'));
    await _storage.delete(_key(serverId, 'endpoint'));
    await _storage.delete(_key(serverId, 'tokenEndpoint'));
    await _storage.delete(_key(serverId, 'loginUri'));
    await _storage.delete(_key(serverId, 'clientId'));
    await _storage.delete(_key(serverId, 'redirectUrl'));
    await _storage.delete(_key(serverId, 'scopes'));
  }
}
