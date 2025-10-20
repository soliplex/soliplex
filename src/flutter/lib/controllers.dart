import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex_client/controllers/app_state_controller.dart';
import 'package:soliplex_client/controllers/current_chatroom_controller.dart';
import 'package:soliplex_client/controllers/pydantic_provider_controller.dart';
import 'package:soliplex_client/controllers/service_url_controller.dart';
import 'package:soliplex_client/controllers/oidc_auth_controller.dart';

final oidcAuthController = StateProvider<OidcAuthController>(
  (_) => throw UnimplementedError(),
);

final appStateController = StateNotifierProvider<AppStateController, AppState>(
  (_) => throw UnimplementedError(),
);

final currentChatroomControllerProvider =
    StateNotifierProvider<CurrentChatroomController, String?>(
      (_) => throw UnimplementedError(),
    );

final pydanticProviderController = StateProvider<PydanticProviderController>(
  (_) => throw UnimplementedError(),
);

final serviceUrlController = StateProvider<ServiceUrlController>(
  (_) => throw UnimplementedError(),
);
