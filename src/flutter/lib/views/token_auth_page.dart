import 'package:flutter/material.dart';

import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:soliplex_client/controllers.dart';
import 'package:soliplex_client/list_extension.dart';
import 'package:soliplex_client/oidc_auth_token_response.dart';
import 'package:soliplex_client/sso_config.dart';

class TokenAuthPage extends ConsumerStatefulWidget {
  final String title;
  final List<SsoConfig> _ssoConfigs;
  final String _appRedirectPath;
  final void Function(String) _setTokenCallback;
  final Widget customUriButton;

  const TokenAuthPage({
    required List<SsoConfig> ssoConfigs,
    required String redirectPathPostAuthentication,
    required void Function(String) setTokenCallback,
    required this.title,
    required this.customUriButton,
    super.key,
  }) : _ssoConfigs = ssoConfigs,
       _appRedirectPath = redirectPathPostAuthentication,
       _setTokenCallback = setTokenCallback;

  @override
  ConsumerState<TokenAuthPage> createState() => _TokenAuthPageState();
}

class _TokenAuthPageState extends ConsumerState<TokenAuthPage> {
  @override
  Widget build(BuildContext context) {
    final oidcController = ref.watch(oidcAuthController);
    final serviceController = ref.watch(serviceUrlController);

    return Center(
      child: Column(
        children: <Widget>[
          const SizedBox(height: 30),
          for (final config in widget._ssoConfigs)
            ElevatedButton(
              onPressed: () async {
                late final OidcAuthTokenResponse result;
                try {
                  result = await oidcController.authorizeAndExchangeCode(
                    config,
                  );
                  final serviceBaseUrl = ref
                      .watch(pydanticProviderController)
                      .baseServiceUrl;
                  serviceController.addServiceUrl(
                    serviceBaseUrl.endsWith('/api')
                        ? serviceBaseUrl.substring(
                            0,
                            serviceBaseUrl.length - '/api'.length,
                          )
                        : serviceBaseUrl,
                  );
                  widget._setTokenCallback(result.accessToken);
                  if (context.mounted) {
                    context.go(widget._appRedirectPath);
                  }
                } on FlutterAppAuthUserCancelledException catch (exception) {
                  debugPrint('User has cancelled the operation: $exception.');
                  if (context.mounted) {
                    await showDialog(
                      context: context,
                      barrierDismissible: false,
                      builder: (context) => Builder(
                        builder: (context) {
                          return AlertDialog(
                            content: SingleChildScrollView(
                              child: Text(
                                'User has cancelled the operation: $exception.',
                              ),
                            ),
                            actions: [
                              TextButton(
                                onPressed: () {
                                  Navigator.pop(context);
                                },
                                child: const Text('OK'),
                              ),
                            ],
                          );
                        },
                      ),
                    );
                  }
                } on FlutterAppAuthPlatformException catch (exception) {
                  debugPrint('Oidc sign in was not successful: $exception.');
                  if (context.mounted) {
                    await showDialog(
                      context: context,
                      barrierDismissible: false,
                      builder: (context) => Builder(
                        builder: (context) {
                          return AlertDialog(
                            content: SingleChildScrollView(
                              child: Text(
                                'Oidc sign in was not successful: $exception.',
                              ),
                            ),
                            actions: [
                              TextButton(
                                onPressed: () {
                                  Navigator.pop(context);
                                },
                                child: const Text('OK'),
                              ),
                            ],
                          );
                        },
                      ),
                    );
                  }
                } catch (e) {
                  debugPrint(e.toString());
                }
              },
              child: Text('Authenticate with ${config.id}'),
            ),
          widget.customUriButton,
        ].interleave(const SizedBox(height: 30)),
      ),
    );
  }
}
