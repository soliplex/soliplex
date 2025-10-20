import 'package:flutter/material.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import 'package:soliplex_client/controllers.dart';
import 'package:soliplex_client/oidc_auth_token_response.dart';
import 'package:soliplex_client/secure_token_storage.dart';

class AuthPage extends ConsumerWidget {
  const AuthPage(
    this._secureTokenStorage,
    this._parameters,
    this._postAuthRedirectUrl, {
    super.key,
  });

  final SecureTokenStorage _secureTokenStorage;
  final Map<String, String> _parameters;
  final String _postAuthRedirectUrl;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final serviceController = ref.read(serviceUrlController);
    final serviceBaseUrl = ref.read(pydanticProviderController).baseServiceUrl;
    serviceController.addServiceUrl(
      serviceBaseUrl.endsWith('/api')
          ? serviceBaseUrl.substring(0, serviceBaseUrl.length - '/api'.length)
          : serviceBaseUrl,
    );
    return FutureBuilder<void>(
      future: _secureTokenStorage.setOidcAuthTokenResponse(
        OidcAuthTokenResponse(
          idToken: _parameters['id_token'] ?? '',
          accessToken: _parameters['token'] ?? '',
          accessTokenExpiration: DateTime.fromMillisecondsSinceEpoch(
            DateTime.now().millisecondsSinceEpoch +
                int.parse(_parameters['expires_in'] ?? '0') * 1000,
          ),
          refreshToken: _parameters['refresh_token'] ?? '',
        ),
      ),
      builder: (BuildContext context, AsyncSnapshot<void> snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return Center(child: CircularProgressIndicator());
        }
        return FutureBuilder(
          future: launchUrl(
            Uri.parse(_postAuthRedirectUrl),
            webOnlyWindowName: '_self',
          ),
          builder: (context, snapshot) {
            if (!snapshot.hasData) {
              return Center(child: CircularProgressIndicator());
            }
            return Container();
          },
        );
      },
    );
  }
}
