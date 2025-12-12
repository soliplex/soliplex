import 'oidc_auth_token_response.dart';
import 'secure_storage_gateway.dart';

class SecureTokenStorage {
  final _oidcIdTokenStorageKey = 'oidc.id';
  final _oidcAccessTokenStorageKey = 'oidc.access';
  final _oidcAccessTokenExpirationStorageKey = 'oidc.expiration';
  final _oidcRefreshTokenStorageKey = 'oidc.refresh';
  final SecureStorageGateway _storage;

  SecureTokenStorage(this._storage);

  Future<void> setOidcAuthTokenResponse(
    OidcAuthTokenResponse tokenResponse,
  ) async {
    await _storage.write(_oidcIdTokenStorageKey, tokenResponse.idToken);
    await _storage.write(_oidcAccessTokenStorageKey, tokenResponse.accessToken);
    await _storage.write(
      _oidcAccessTokenExpirationStorageKey,
      '${tokenResponse.accessTokenExpiration.millisecondsSinceEpoch}',
    );
    await _storage.write(
      _oidcRefreshTokenStorageKey,
      tokenResponse.refreshToken,
    );
  }

  Future<OidcAuthTokenResponse?> getOidcAuthTokenResponse() async {
    final idToken = await _storage.read(_oidcIdTokenStorageKey);
    final accessToken = await _storage.read(_oidcAccessTokenStorageKey);
    final expiration = await _storage.read(
      _oidcAccessTokenExpirationStorageKey,
    );
    final refreshToken = await _storage.read(_oidcRefreshTokenStorageKey);

    if (idToken == null ||
        accessToken == null ||
        expiration == null ||
        refreshToken == null) {
      return null;
    }

    return OidcAuthTokenResponse(
      idToken: idToken,
      accessToken: accessToken,
      accessTokenExpiration: DateTime.fromMillisecondsSinceEpoch(
        int.parse(expiration),
      ),
      refreshToken: refreshToken,
    );
  }

  Future<String?> getOidcRefreshToken() async {
    final refreshToken = await _storage.read(_oidcRefreshTokenStorageKey);

    if (refreshToken == null) {
      return null;
    }

    return refreshToken;
  }

  Future<void> deleteOidcAuthTokenResponse() async {
    await _storage.delete(_oidcIdTokenStorageKey);
    await _storage.delete(_oidcAccessTokenStorageKey);
    await _storage.delete(_oidcAccessTokenExpirationStorageKey);
    await _storage.delete(_oidcRefreshTokenStorageKey);
  }
}
