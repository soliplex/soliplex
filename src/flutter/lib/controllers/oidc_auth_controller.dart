import 'package:soliplex_client/oidc_auth_interactor.dart';
import 'package:soliplex_client/oidc_auth_token_response.dart';
import 'package:soliplex_client/sso_config.dart';

class OidcAuthController {
  final OidcAuthInteractor oidcAuthInteractor;

  OidcAuthController(this.oidcAuthInteractor);

  Future<OidcAuthTokenResponse> authorizeAndExchangeCode(
    SsoConfig config,
  ) async => oidcAuthInteractor.authorizeAndExchangeCode(config);
}
