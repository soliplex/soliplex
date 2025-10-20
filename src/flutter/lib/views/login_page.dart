import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:soliplex_client/controllers.dart';
import 'package:soliplex_client/controllers/pydantic_provider_controller.dart';
import 'package:soliplex_client/controllers/service_url_controller.dart';
import 'package:soliplex_client/sso_config.dart';
import 'package:soliplex_client/views/browser_auth_page.dart';
import 'package:soliplex_client/views/token_auth_page.dart';

class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({
    required this.title,
    required this.ssoConfigs,
    required this.redirectPathPostAuthentication,
    required this.setTokenCallback,
    required this.isLoggedInCallback,
    super.key,
  });

  final String title;
  final List<SsoConfig> ssoConfigs;
  final String redirectPathPostAuthentication;
  final Function(String) setTokenCallback;
  final Future<bool> Function(WidgetRef ref) isLoggedInCallback;

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  Future<bool> _checkLogInStatus() async {
    final isLoggedIn = await widget.isLoggedInCallback(ref);
    if (isLoggedIn && mounted) {
      context.go('/chat');
    }
    return isLoggedIn;
  }

  void setSsoConfigs(List<SsoConfig> newConfigs) {
    setState(() {
      ssoConfigs = newConfigs;
    });
  }

  List<SsoConfig>? ssoConfigs;

  Widget _buildLoginPage() {
    final chatroomController = ref.read(
      currentChatroomControllerProvider.notifier,
    );

    return FutureBuilder(
      future: chatroomController.requestLoginSystems(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return CircularProgressIndicator(); // Show loading indicator
        } else if (snapshot.hasError) {
          final errorText = 'Error: ${snapshot.error}';
          debugPrint(errorText);
          return Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                color: Theme.of(context).scaffoldBackgroundColor,
                padding: EdgeInsets.all(16.0),
                child: Text(errorText),
              ),
              CustomUrlButton(
                ssoConfigs: widget.ssoConfigs,
                onConfirm: (newConfigs) {
                  setSsoConfigs(newConfigs);
                },
              ),
            ],
          ); // Show error
        } else if (snapshot.hasData) {
          final validSystemNames = snapshot.data ?? [];

          final workingSso = ssoConfigs ?? widget.ssoConfigs;

          final validSso = workingSso.where((e) {
            return validSystemNames.contains(e.id.toLowerCase());
          }).toList();

          if (validSso.isEmpty) {
            return Column(
              spacing: 16.0,
              children: [
                (ElevatedButton(
                  onPressed: () {
                    context.go('/chat');
                  },
                  child: Text('Authentication disabled. Click to start'),
                )),
                kIsWeb
                    ? Container()
                    : CustomUrlButton(
                        ssoConfigs: validSso,
                        onConfirm: (newConfigs) {
                          setSsoConfigs(newConfigs);
                        },
                      ),
              ],
            );
          }

          ref.read(oidcAuthController).oidcAuthInteractor.useAuth = true;

          final customUriButton = CustomUrlButton(
            ssoConfigs: validSso,
            onConfirm: (newConfigs) {
              setSsoConfigs(newConfigs);
            },
          );

          return kIsWeb
              ? BrowserAuthPage(
                  validSso,
                  title: widget.title,
                  customUriButton: customUriButton,
                )
              : TokenAuthPage(
                  ssoConfigs: validSso,
                  setTokenCallback: widget.setTokenCallback,
                  title: widget.title,
                  customUriButton: customUriButton,
                  redirectPathPostAuthentication:
                      widget.redirectPathPostAuthentication,
                );
        } else {
          return Text('Retrieved login info');
        }
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder(
      future: _checkLogInStatus(),
      builder: (context, snapshot) {
        final isLoggedIn = snapshot.data;
        if (isLoggedIn == null) {
          return CircularProgressIndicator();
        } else {
          return isLoggedIn
              ?
                // Will be redirected to /chat page
                CircularProgressIndicator()
              : _buildLoginPage();
        }
      },
    );
  }
}

class CustomUrlButton extends ConsumerWidget {
  const CustomUrlButton({
    required this.ssoConfigs,
    required this.onConfirm,
    super.key,
  });

  final List<SsoConfig> ssoConfigs;
  final Function(List<SsoConfig>)? onConfirm;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ElevatedButton(
      onPressed: () async {
        final currentConfig = ref.read(pydanticProviderController);
        final presetUrls = await ref
            .read(serviceUrlController)
            .getAllServiceUrl();

        final serviceController = ref.read(serviceUrlController);

        if (context.mounted) {
          final newUrl = await showDialog<String>(
            context: context,
            builder: (context) {
              final destinationUri = Uri.parse(currentConfig.destinationUrl);

              final destinationOrigin = destinationUri.origin;

              final originController = TextEditingController.fromValue(
                TextEditingValue(text: destinationOrigin),
              );

              return AlertDialog(
                title: Text('Custom URL'),
                content: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (presetUrls.isNotEmpty) ...[
                        PresetUrlsSelector(presetUrls, serviceController),
                        Divider(),
                      ],
                      Text(
                        'Custom Path',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: Colors.blueGrey[800],
                        ),
                      ),
                      TextField(controller: originController),
                    ],
                  ),
                ),
                actions: [
                  ElevatedButton(
                    onPressed: () {
                      context.pop();
                    },
                    child: Text('Cancel'),
                  ),
                  ElevatedButton(
                    onPressed: () {
                      context.pop(originController.text);
                    },
                    child: Text('Submit'),
                  ),
                ],
              );
            },
          );

          if (newUrl != null) {
            try {
              final newUri = Uri.parse(newUrl);
              List<SsoConfig> newConfigs = [];
              for (final config in ssoConfigs) {
                final currentLoginUrl = config.loginUrl;
                final newLoginUrl = currentLoginUrl.replace(
                  scheme: newUri.scheme,
                  host: newUri.host,
                  port: newUri.port,
                  queryParameters: currentLoginUrl.queryParameters,
                );

                newConfigs.add(SsoConfig.newEndpoint(newLoginUrl, config));
              }

              ref.read(oidcAuthController).oidcAuthInteractor.useAuth = false;

              final pydanticController = ref
                  .read(pydanticProviderController.notifier)
                  .update(
                    (_) =>
                        PydanticProviderController.newDestinationUrlFromExistingController(
                          '$newUrl/api',
                          currentConfig,
                        ),
                  );

              ref
                  .read(currentChatroomControllerProvider.notifier)
                  .setNewProvider('$newUrl/api', pydanticController.oidcClient);

              onConfirm != null ? onConfirm!(newConfigs) : null;
            } catch (e) {
              debugPrint(
                'Exception occurred while setting new url config:'
                '\n$e',
              );
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('`$newUrl` is not a valid uri.')),
                );
              }
            }
          }
        }
      },
      child: Text('Custom URL'),
    );
  }
}

class PresetUrlsSelector extends StatefulWidget {
  const PresetUrlsSelector(this.presetUrls, this.urlController, {super.key});

  final Set<String> presetUrls;
  final ServiceUrlController urlController;

  @override
  State<PresetUrlsSelector> createState() => _PresetUrlsSelectorState();
}

class _PresetUrlsSelectorState extends State<PresetUrlsSelector> {
  late final Set<String> urls;

  @override
  void initState() {
    super.initState();
    urls = widget.presetUrls;
  }

  @override
  Widget build(BuildContext context) {
    return DropdownButton(
      value: null,
      hint: Text('Preset URLs'),
      items: urls.map<DropdownMenuItem<String>>((String value) {
        return DropdownMenuItem<String>(
          value: value,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(value),
              IconButton(
                onPressed: () async {
                  final confirmation = await showDialog<bool>(
                    context: context,
                    builder: (context) => AlertDialog(
                      content: Text('Are you sure you want to delete: $value?'),
                      actions: [
                        ElevatedButton(
                          onPressed: () {
                            context.pop();
                          },
                          child: Text('Cancel'),
                        ),
                        ElevatedButton(
                          onPressed: () {
                            context.pop(true);
                          },
                          child: Text('Submit'),
                        ),
                      ],
                    ),
                  );

                  if (confirmation == true) {
                    widget.urlController.deleteServiceUrl(value);
                    setState(() {
                      urls.remove(value);
                    });
                    if (context.mounted) {
                      context.pop();
                    }
                  }
                },
                icon: Icon(Icons.delete),
              ),
            ],
          ),
        );
      }).toList(),
      onChanged: (e) => context.pop(e),
      focusColor: Theme.of(context).canvasColor,
    );
  }
}
