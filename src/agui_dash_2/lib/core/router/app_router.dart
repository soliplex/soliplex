import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/app_providers.dart';
import '../../features/chat/chat_screen.dart';
import '../../features/endpoints/endpoint_list_screen.dart';
import '../../features/inspector/network_inspector_screen.dart';
import '../../features/server/server_setup_screen.dart';
import '../../features/navigation/app_scaffold.dart';

final _rootNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'root');
final _shellNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'shell');

final routerProvider = Provider<GoRouter>((ref) {
  final notifier = RouterNotifier(ref);
  
  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    refreshListenable: notifier,
    initialLocation: '/chat',
    debugLogDiagnostics: true,
    redirect: (context, state) {
      final appStateAsync = ref.read(appStateStreamProvider);
      final appState = appStateAsync.valueOrNull;
      
      // 1. Auth Guard
      if (appState is! AppStateReady) {
        if (state.matchedLocation != '/setup') {
          return '/setup';
        }
        return null;
      }
      
      // 2. Setup Guard
      // Allow explicit navigation to /setup for switching servers.
      // if (state.matchedLocation == '/setup') {
      //   return '/chat';
      // }
      
      return null;
    },
    routes: [
      GoRoute(
        path: '/setup',
        builder: (context, state) => ServerSetupScreen(
          onConnected: () => context.go('/chat'),
        ),
      ),
      ShellRoute(
        navigatorKey: _shellNavigatorKey,
        builder: (context, state, child) => AppScaffold(child: child),
        routes: [
          GoRoute(
            path: '/chat',
            builder: (context, state) => const ChatScreen(),
            routes: [
              GoRoute(
                path: ':roomId',
                builder: (context, state) {
                  final roomId = state.pathParameters['roomId'];
                  return ChatScreen(roomId: roomId);
                },
              ),
            ],
          ),
          GoRoute(
            path: '/settings',
            builder: (context, state) => const EndpointListScreen(),
          ),
          GoRoute(
            path: '/inspector',
            builder: (context, state) => const NetworkInspectorScreen(),
          ),
        ],
      ),
    ],
  );
});

class RouterNotifier extends ChangeNotifier {
  final Ref _ref;
  
  RouterNotifier(this._ref) {
    _ref.listen(appStateStreamProvider, (_, __) => notifyListeners());
  }
}
