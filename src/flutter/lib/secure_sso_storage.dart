import 'secure_storage_gateway.dart';
import 'sso_config.dart';

class SecureSsoStorage {
  final _ssoIdKey = 'sso.id';
  final _ssoTitleKey = 'sso.title';
  final _ssoEndpointKey = 'sso.endpoint';
  final _ssoTokenEndpointKey = 'sso.token.endpoint';
  final _ssoLoginUriKey = 'sso.login.uri';
  final _ssoClientIdStorageKey = 'sso.client.id';
  final _ssoRedirectUrlStorageKey = 'sso.redirect.url';
  final _ssoScopesStorageKey = 'sso.scopes';

  final SecureStorageGateway _storage;

  SecureSsoStorage(this._storage);

  Future<void> setSsoConfig(SsoConfig config) async {
    await _storage.write(_ssoIdKey, config.id);
    await _storage.write(_ssoTitleKey, config.title);
    await _storage.write(_ssoEndpointKey, config.endpoint);
    await _storage.write(_ssoTokenEndpointKey, config.tokenEndpoint);
    await _storage.write(_ssoLoginUriKey, config.loginUrl.toString());
    await _storage.write(_ssoClientIdStorageKey, config.clientId);
    await _storage.write(_ssoRedirectUrlStorageKey, config.redirectUrl);
    await _storage.write(_ssoScopesStorageKey, config.scopes.join(','));
  }

  Future<SsoConfig?> getSsoConfig() async {
    final id = await _storage.read(_ssoIdKey);
    final title = await _storage.read(_ssoTitleKey);
    final endpoint = await _storage.read(_ssoEndpointKey);
    final tokenEndpoint = await _storage.read(_ssoTokenEndpointKey);
    final loginUri = await _storage.read(_ssoLoginUriKey);
    final clientId = await _storage.read(_ssoClientIdStorageKey);
    final redirectUrl = await _storage.read(_ssoRedirectUrlStorageKey);
    final scopes = await _storage.read(_ssoScopesStorageKey);

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

  Future<void> deleteSsoConfig() async {
    await _storage.delete(_ssoIdKey);
    await _storage.delete(_ssoEndpointKey);
    await _storage.delete(_ssoTokenEndpointKey);
    await _storage.delete(_ssoLoginUriKey);
    await _storage.delete(_ssoClientIdStorageKey);
    await _storage.delete(_ssoRedirectUrlStorageKey);
    await _storage.delete(_ssoScopesStorageKey);
  }
}
