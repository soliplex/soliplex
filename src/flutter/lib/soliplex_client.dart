import 'dart:convert';

import 'package:flutter/material.dart';

import 'package:flutter_ai_toolkit/flutter_ai_toolkit.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';

import 'package:soliplex_client/secure_token_storage.dart';
import 'package:soliplex_client/shared_widgets/background_image_stack.dart';
import 'package:soliplex_client/shared_widgets/soliplex_client_appbar.dart';
import 'package:soliplex_client/views/auth_page.dart';
import 'package:soliplex_client/views/chatroom.dart';
import 'package:soliplex_client/views/load_chatrooms_page.dart';
import 'package:soliplex_client/views/map_page.dart';

import 'controllers.dart';

class SoliplexClient extends ConsumerWidget {
  final String title;
  final Widget loginPage;
  final SecureTokenStorage secureTokenStorage;
  final String postAuthRedirectUrl;

  const SoliplexClient({
    required this.title,
    required this.loginPage,
    required this.secureTokenStorage,
    required this.postAuthRedirectUrl,
    super.key,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.light(primary: Colors.black),
        useMaterial3: true,
      ),
      routerConfig: GoRouter(
        routes: [
          ShellRoute(
            pageBuilder: (context, state, child) {
              return NoTransitionPage(
                child: Scaffold(appBar: SoliplexAppBar(), body: child),
              );
            },
            routes: [
              GoRoute(
                path: '/',
                pageBuilder: (context, state) {
                  final appState = ref.read(appStateController);
                  appState.title = null;
                  appState.canNavigate = false;

                  return NoTransitionPage(
                    child: BackgroundImageStack(
                      image: AssetImage('assets/images/ic_launcher.png'),
                      top: 100.0,
                      bottom: 45.0,
                      opacity: .75,
                      child: loginPage,
                    ),
                  );
                },
              ),
              GoRoute(
                path: '/auth',
                pageBuilder: (context, state) {
                  ref.read(oidcAuthController).oidcAuthInteractor.useAuth =
                      true;

                  final appState = ref.read(appStateController);
                  appState.title = null;
                  appState.canNavigate = false;

                  return NoTransitionPage(
                    child: AuthPage(
                      secureTokenStorage,
                      state.uri.queryParameters,
                      postAuthRedirectUrl,
                    ),
                  );
                },
              ),
              GoRoute(
                path: '/chat',
                pageBuilder: (context, state) {
                  final appState = ref.read(appStateController);
                  appState.title = 'ROOMS';
                  appState.canNavigate = false;

                  return NoTransitionPage(
                    child: Center(child: LoadChatroomsPage()),
                  );
                },
              ),
              GoRoute(
                path: '/chat/:roomId',
                pageBuilder: (context, state) {
                  final chatroomController = ref.read(
                    currentChatroomControllerProvider.notifier,
                  );

                  final appStateNotifier = ref.read(
                    appStateController.notifier,
                  );

                  List<ChatMessage>? initialHistory;
                  if (state.extra != null &&
                      state.extra is List<ChatMessage>?) {
                    initialHistory = state.extra as List<ChatMessage>;
                  }

                  final provider = ref
                      .read(pydanticProviderController)
                      .buildProvider(
                        chatroomController: chatroomController,
                        appStateController: appStateNotifier,
                        initialHistory: initialHistory,
                      );

                  final appState = ref.read(appStateController);
                  appState.title = state.pathParameters['roomId']!;
                  appState.canNavigate = true;

                  return NoTransitionPage(
                    child: Chatroom(llmProvider: provider),
                  );
                },
                redirect: (context, state) async {
                  final chatroomController = ref.read(
                    currentChatroomControllerProvider.notifier,
                  );

                  final storedRoomId = chatroomController
                      .currentChatPageConfig
                      .roomConfig
                      .roomId;

                  final destinationRoomId = state.pathParameters['roomId'];

                  if (destinationRoomId != null &&
                      destinationRoomId != storedRoomId) {
                    try {
                      final roomConfig = await chatroomController
                          .requestChatroom(destinationRoomId);

                      final bgImage = await chatroomController
                          .retrieveChatroomBgImage(destinationRoomId);

                      chatroomController.setCurrentChatPageConfig(
                        roomId: destinationRoomId,
                        welcomeMessage: roomConfig.welcomeMessage,
                        suggestions: roomConfig.suggestions,
                        enableAttachments: roomConfig.enableAttachments,
                        imageBytes: bgImage,
                      );
                    } catch (e) {
                      debugPrint(
                        'Received error while retrieving chatroom $destinationRoomId: $e',
                      );
                      if (context.mounted) {
                        ScaffoldMessenger.of(
                          context,
                        ).showSnackBar(SnackBar(content: Text(e.toString())));
                      }
                      return '/chat';
                    }
                  }
                  return null;
                },
              ),
              GoRoute(
                path: '/quiz/:quizId',
                pageBuilder: (context, state) {
                  final chatroomController = ref.read(
                    currentChatroomControllerProvider.notifier,
                  );

                  final appStateNotifier = ref.read(
                    appStateController.notifier,
                  );

                  final provider = ref
                      .read(pydanticProviderController)
                      .buildProvider(
                        chatroomController: chatroomController,
                        appStateController: appStateNotifier,
                        initialHistory: [],
                      );

                  final appState = ref.read(appStateController);
                  appState.title = chatroomController
                      .currentChatPageConfig
                      .roomConfig
                      .roomId;
                  appState.canNavigate = true;

                  return NoTransitionPage(
                    child: Chatroom(
                      llmProvider: provider,
                      quizId: state.pathParameters['quizId']!,
                    ),
                  );
                },
              ),
              GoRoute(
                path: '/map',
                pageBuilder: (context, state) {
                  final appState = ref.read(appStateController);
                  appState.title = 'MAPS';
                  appState.canNavigate = true;
                  if (state.extra != null && state.extra is List<Position>) {
                    return NoTransitionPage(
                      child: MapPage(state.extra! as List<Position>),
                    );
                  }
                  try {
                    final queryParameters = state.uri.queryParameters;
                    final positions = extractGeolocationPositions(
                      queryParameters,
                    );

                    if (positions.isNotEmpty) {
                      return NoTransitionPage(child: MapPage(positions));
                    }
                    return NoTransitionPage(child: MapPage([]));
                  } catch (e) {
                    debugPrint(
                      'Exception occurred while handling /map route.'
                      '\n$e',
                    );
                    return NoTransitionPage(child: MapPage([]));
                  }
                },
              ),
            ],
          ),
        ],
      ),
    );
  }

  List<Position> extractGeolocationPositions(
    Map<String, String> queryParameters,
  ) {
    final coordinatesJson = queryParameters['coords'] ?? '[]';
    final List coordinates = jsonDecode(coordinatesJson);

    final positions = <Position>[];
    for (final coordinate in coordinates) {
      positions.add(
        Position(
          latitude: double.tryParse('${coordinate['lat']}') ?? 0.0,
          longitude: double.tryParse('${coordinate['lng']}') ?? 0.0,
          timestamp: int.tryParse('${coordinate['time']}') == null
              ? DateTime.now()
              : DateTime.fromMillisecondsSinceEpoch(
                  int.parse('${coordinate['time']}'),
                ),
          accuracy: double.tryParse('${coordinate['acc']}') ?? 0.0,
          altitude: double.tryParse('${coordinate['alt']}') ?? 0.0,
          altitudeAccuracy: double.tryParse('${coordinate['alt-acc']}') ?? 0,
          heading: double.tryParse('${coordinate['head']}') ?? 0.0,
          headingAccuracy: double.tryParse('${coordinate['head-acc']}') ?? 0.0,
          speed: double.tryParse('${coordinate['speed']}') ?? 0.0,
          speedAccuracy: double.tryParse('${coordinate['speed-acc']}') ?? 0.0,
        ),
      );
    }
    return positions;
  }
}
