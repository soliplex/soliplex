import 'package:flutter/material.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex_client/controllers.dart';
import 'package:soliplex_client/list_extension.dart';
import 'package:soliplex_client/sso_config.dart';

class BrowserAuthPage extends ConsumerWidget {
  final String title;
  final List<SsoConfig> configurations;
  final Widget customUriButton;

  const BrowserAuthPage(
    this.configurations, {
    required this.title,
    required this.customUriButton,
    super.key,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final oidcController = ref.read(oidcAuthController);
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.start,
        children: <Widget>[
          const SizedBox(height: 60),
          for (final config in configurations)
            ElevatedButton(
              onPressed: () async {
                try {
                  await oidcController.authorizeAndExchangeCode(config);

                  return;
                } catch (e) {
                  debugPrint(e.toString());
                }
              },
              child: Text('Authenticate with ${config.id}'),
            ),
          customUriButton,
        ].interleave(const SizedBox(height: 30)),
      ),
    );
  }
}
