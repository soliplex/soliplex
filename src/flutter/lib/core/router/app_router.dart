import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:soliplex/core/providers/app_providers.dart';
import 'package:soliplex/core/utils/debug_log.dart';
import 'package:soliplex/features/auth/auth_callback_screen.dart';
import 'package:soliplex/features/chat/chat_screen.dart';
import 'package:soliplex/features/endpoints/endpoint_list_screen.dart';
import 'package:soliplex/features/inspector/network_inspector_screen.dart';
import 'package:soliplex/features/navigation/app_scaffold.dart';
import 'package:soliplex/features/server/server_setup_screen.dart';

final _rootNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'root');
final _shellNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'shell');

final routerProvider = Provider<GoRouter>((ref) {
  final notifier = RouterNotifier(ref);

  // On web, use the browser URL; otherwise default to /chat
  const initialLocation = kIsWeb ? null : '/chat';

  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    refreshListenable: notifier,
    initialLocation: initialLocation,
    debugLogDiagnostics: true,
    redirect: (context, state) {
      final appStateAsync = ref.read(appStateStreamProvider);
      final appState = appStateAsync.valueOrNull;
      final location = state.matchedLocation;
      final uri = state.uri;

      DebugLog.auth(
        'Router redirect: location=$location, uri=$uri, appState=$appState',
      );

      // Allow auth callback route to bypass auth guard (handles its own auth)
      // Web auth callback is /api/auth/{system} (e.g., /api/auth/keycloak)
      if (uri.path.startsWith('/api/auth/')) {
        DebugLog.auth('Router: Auth callback detected, bypassing guard');
        return null;
      }

      // 1. Auth Guard
      if (appState is! AppStateReady) {
        if (location != '/setup') {
          DebugLog.auth('Router: Not ready, redirecting to /setup');
          return '/setup';
        }
        return null;
      }

      return null;
    },
    routes: [
      // Auth callback route - handles OIDC redirect (must be before ShellRoute)
      // Web auth callback is /api/auth/{system} (e.g., /api/auth/keycloak)
      GoRoute(
        path: '/api/auth/:system',
        builder: (context, state) => const AuthCallbackScreen(),
      ),
      GoRoute(
        path: '/setup',
        builder: (context, state) =>
            ServerSetupScreen(onConnected: () => context.go('/chat')),
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
  RouterNotifier(this._ref) {
    _ref.listen(appStateStreamProvider, (_, next) => notifyListeners());
  }
  final Ref _ref;
}
