import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:soliplex_client/controllers.dart';
import 'package:soliplex_client/controllers/app_state_controller.dart';
import 'package:soliplex_client/controllers/current_chatroom_controller.dart';
import 'package:soliplex_client/controllers/oidc_auth_controller.dart';
import 'package:soliplex_client/controllers/pydantic_provider_controller.dart';
import 'package:soliplex_client/controllers/service_url_controller.dart';
import 'package:soliplex_client/oidc_auth_interactor.dart';
import 'package:soliplex_client/oidc_client.dart';
import 'package:soliplex_client/secure_url_storage.dart';
import 'package:soliplex_client/views/login_page.dart';

import 'secure_sso_storage.dart';
import 'secure_storage_gateway.dart';
import 'secure_token_storage.dart';
import 'soliplex_client.dart';
import 'sso_config.dart';

Future<Widget> configure() async {
  const appTitle = 'Soliplex Client';

  const version = 'v1';
  const defaultRoomId = 'default';

  // Frontend site url
  late final String clientSiteUrl;
  // Backend service url
  late final String serviceUrl;

  const servicePortArg = String.fromEnvironment('SERVICE_PORT');

  if (kIsWeb) {
    final baseUri = Uri.base;

    final scheme = baseUri.scheme;
    final host = baseUri.host;

    int port = baseUri.port;
    if (servicePortArg.isNotEmpty) {
      port = int.tryParse(servicePortArg) ?? baseUri.port;
    } else if (baseUri.port == 59001) {
      port = 8000;
    } else if (baseUri.port == 443) {
      port = 0;
    }

    clientSiteUrl = '$scheme://$host${port == 0 ? '' : ':${baseUri.port}'}';
    serviceUrl = '$scheme://$host${port == 0 ? '' : ':$port'}';
  } else {
    clientSiteUrl = 'ai.soliplex.client';

    const serviceUrlArg = String.fromEnvironment('SERVICE_URL');

    if (serviceUrlArg.isEmpty) {
      throw Exception(
        'For all non-web platforms, "SERVICE_URL" argument must be provided.',
      );
    }
    final port = int.tryParse(servicePortArg);
    if (servicePortArg.isEmpty || port == null) {
      serviceUrl = serviceUrlArg;
    } else {
      serviceUrl = '$serviceUrlArg${port == 0 ? '' : ':$port'}';
    }
  }

  final baseServiceUrl = appendUrl(serviceUrl, '/api');

  // retrieve login urls from `/api/login`
  final webAuthUrl = appendUrl(clientSiteUrl, '/#/auth');
  final webChatUrl = appendUrl(clientSiteUrl, '/#/chat');

  // The scopes of the sso configs don't affect web.
  final ssoConfigurations = <SsoConfig>[];

  try {
    final httpClient = http.Client();
    final loginEndpointsResponse = await httpClient.get(
      Uri.parse(appendUrl(baseServiceUrl, '/login')),
    );

    final Map<String, dynamic> loginEndpointsJson = jsonDecode(
      loginEndpointsResponse.body,
    );

    debugPrint('loginEndpointsJson: $loginEndpointsJson');

    for (final Map<String, dynamic> endpoint in loginEndpointsJson.values) {
      try {
        final loginRedirectUri = Uri.parse(
          appendUrl(baseServiceUrl, 'login/${endpoint['id']!}'),
        ).replace(queryParameters: {'return_to': webAuthUrl});

        final endpointConfig = SsoConfig(
          id: endpoint['id']!,
          title: endpoint['title']!,
          endpoint: endpoint['server_url']!,
          tokenEndpoint:
              '${endpoint['server_url']}/protocol/openid-connect/token',
          loginUrl: loginRedirectUri,
          clientId: endpoint['client_id']!,
          // TODO: rename. mobile app re-entry link
          redirectUrl: 'ai.soliplex.client:/',
          scopes: ['openid', 'email', 'profile', 'offline_access'],
        );
        ssoConfigurations.add(endpointConfig);
      } catch (e) {
        debugPrint(
          'Exception occurred while extracting login endpoint: $endpoint'
          '\n$e',
        );
        continue;
      }
    }
  } catch (e) {
    debugPrint('Exception while fetching login systesm from backend.\n$e');
  }

  final secureStorage = SecureStorageGateway(FlutterSecureStorage());

  final secureSsoStorage = SecureSsoStorage(secureStorage);
  final secureTokenStorage = SecureTokenStorage(secureStorage);

  // How early before OIDC Auth token expiration to preform a refresh
  const tokenExpirationBuffer = Duration(seconds: 30);

  final oidcInteractor = kIsWeb
      ? OidcWebAuthInteractor(
          secureSsoStorage,
          secureTokenStorage,
          tokenExpirationBuffer,
        )
      : OidcMobileAuthInteractor(
          FlutterAppAuth(),
          secureSsoStorage,
          secureTokenStorage,
          tokenExpirationBuffer,
        );

  final oidcController = OidcAuthController(oidcInteractor);

  const maxRequestRetries = 1;

  final oidcClient = OidcClient(
    http.Client(),
    oidcInteractor,
    maxRetries: maxRequestRetries,
  );

  final validChatVariables = ['CURRENT_GEOLOCATION'];

  final pydanticController = PydanticProviderController(
    baseServiceUrl: baseServiceUrl,
    destinationUrl: appendUrl(baseServiceUrl, '/$version/convos'),
    destinationQuizUrl: appendUrl(baseServiceUrl, '/$version/rooms'),
    oidcClient: oidcClient,
    chatVariables: validChatVariables,
  );

  String postAuthRedirectPath = '/chat';

  final chatroomProvider = RemoteChatroomProvider(
    baseEndpoint: baseServiceUrl,
    oidcClient: oidcClient,
  );

  final shortTimeoutDuration = Duration(seconds: 5);
  final longTimeoutDuration = Duration(seconds: 180);

  final currentChatroomController = CurrentChatroomController(
    chatroomProvider,
    defaultRoomId: defaultRoomId,
    shortTimeoutDuration: shortTimeoutDuration,
    longTimeoutDuration: longTimeoutDuration,
  );

  final Widget loginPage = LoginPage(
    title: appTitle,
    ssoConfigs: ssoConfigurations,
    isLoggedInCallback: (WidgetRef ref) async {
      if (kIsWeb) {
        return false;
      }
      final selectedConfig = await secureSsoStorage.getSsoConfig();
      if (selectedConfig != null) {
        try {
          oidcInteractor.useAuth = true;
          await chatroomProvider.listAvailableChatrooms();
          final loginUri = selectedConfig.loginUrl;
          final newApiUrl = '${loginUri.origin}/api';

          final newProvider =
              PydanticProviderController.newDestinationUrlFromExistingController(
                newApiUrl,
                pydanticController,
              );

          // Replace pydanticController with new one using retrieved url
          ref
              .read(pydanticProviderController.notifier)
              .update((_) => newProvider);
          currentChatroomController.setNewProvider(
            newApiUrl,
            newProvider.oidcClient,
          );
          return true;
        } catch (e) {
          oidcInteractor.useAuth = false;
          return false;
        }
      } else {
        oidcInteractor.useAuth = false;
        return false;
      }
    },
    setTokenCallback: (String token) {
      // OpenAI.apiKey = token;
    },
    redirectPathPostAuthentication: postAuthRedirectPath,
  );

  return ProviderScope(
    overrides: [
      appStateController.overrideWith((_) => AppStateController(AppState())),
      oidcAuthController.overrideWith((_) => oidcController),
      currentChatroomControllerProvider.overrideWith(
        (_) => currentChatroomController,
      ),
      pydanticProviderController.overrideWith((_) => pydanticController),
      serviceUrlController.overrideWith(
        (_) => ServiceUrlController(SecureUrlStorage(secureStorage)),
      ),
    ],
    child: SoliplexClient(
      title: appTitle,
      loginPage: loginPage,
      secureTokenStorage: secureTokenStorage,
      postAuthRedirectUrl: webChatUrl,
    ),
  );
}

String appendUrl(String base, String path) {
  // Check if the base URL ends with a slash
  final bool baseEndsWithSlash = base.endsWith('/');

  // Check if the path starts with a slash
  final bool pathStartsWithSlash = path.startsWith('/');

  if (baseEndsWithSlash && pathStartsWithSlash) {
    // If both have slashes, remove one from the path
    return base + path.substring(1);
  } else if ((baseEndsWithSlash && !pathStartsWithSlash) ||
      (!baseEndsWithSlash && pathStartsWithSlash)) {
    // If one has a slash and the other doesn't, just join them
    return base + path;
  } else {
    // if (!baseEndsWithSlash && !pathStartsWithSlash)
    // If neither has a slash, add one in between
    return '$base/$path';
  }
}
