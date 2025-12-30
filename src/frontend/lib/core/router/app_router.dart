import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:soliplex_frontend/core/router/router_notifier.dart';
import 'package:soliplex_frontend/features/home/home_screen.dart';
import 'package:soliplex_frontend/features/login/auth_callback_screen.dart';
import 'package:soliplex_frontend/features/login/login_screen.dart';
import 'package:soliplex_frontend/features/room/room_screen.dart';
import 'package:soliplex_frontend/features/rooms/rooms_screen.dart';
import 'package:soliplex_frontend/features/settings/settings_screen.dart';
import 'package:soliplex_frontend/shared/widgets/app_shell.dart';
import 'package:soliplex_frontend/shared/widgets/shell_config.dart';

/// Settings button for AppBar actions.
///
/// Navigates to the settings screen when pressed.
class _SettingsButton extends StatelessWidget {
  const _SettingsButton();

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Settings',
      child: IconButton(
        icon: const Icon(Icons.settings),
        onPressed: () => context.push('/settings'),
        tooltip: 'Open settings',
      ),
    );
  }
}

/// Creates an AppShell with the given configuration.
AppShell _staticShell({
  required Widget title,
  required Widget body,
  List<Widget> actions = const [],
}) {
  return AppShell(
    config: ShellConfig(title: title, actions: actions),
    body: body,
  );
}

/// Creates a NoTransitionPage with AppShell for static screens.
NoTransitionPage<void> _staticPage({
  required Widget title,
  required Widget body,
  List<Widget> actions = const [],
}) {
  return NoTransitionPage(
    child: _staticShell(title: title, body: body, actions: actions),
  );
}

/// Routes that don't require authentication.
const _publicRoutes = {'/login', '/auth/callback'};

/// Provider for the application router.
///
/// Integrates with appStateProvider via [RouterNotifier] to automatically
/// redirect based on authentication state:
/// - Unauthenticated users are redirected to /login
/// - Authenticated users on /login are redirected to /
/// - Auth callback route is always accessible during auth flow
final routerProvider = Provider<GoRouter>((ref) {
  final notifier = ref.watch(routerNotifierProvider);

  return GoRouter(
    initialLocation: '/',
    refreshListenable: notifier,
    redirect: (context, state) {
      final isPublicRoute = _publicRoutes.contains(state.matchedLocation);
      final isAuthenticated = notifier.isAuthenticated;
      final isInAuthFlow = notifier.isInAuthFlow;

      // Allow callback route during authentication
      if (state.matchedLocation == '/auth/callback') {
        return null;
      }

      // Redirect to login if not authenticated (unless already going there).
      // This covers AppStateNoServer, AppStateNeedsAuth, and AppStateError.
      // During auth flow (probing or authenticating), stay on login screen.
      if (!isAuthenticated && !isInAuthFlow && !isPublicRoute) {
        // Preserve the original location to redirect back after login
        final from = state.matchedLocation;
        if (from != '/') {
          return '/login?from=${Uri.encodeComponent(from)}';
        }
        return '/login';
      }

      // Redirect away from login if already authenticated
      if (isAuthenticated && state.matchedLocation == '/login') {
        // Check if there's a return location
        final from = state.uri.queryParameters['from'];
        if (from != null) {
          final decoded = Uri.decodeComponent(from);
          // Only allow relative paths to prevent open redirect attacks
          if (decoded.startsWith('/') && !decoded.startsWith('//')) {
            return decoded;
          }
        }
        return '/';
      }

      // No redirect needed
      return null;
    },
    routes: [
      // Public routes
      GoRoute(
        path: '/login',
        name: 'login',
        pageBuilder: (context, state) => const NoTransitionPage(
          child: LoginScreen(),
        ),
      ),
      GoRoute(
        path: '/auth/callback',
        name: 'auth-callback',
        pageBuilder: (context, state) => const NoTransitionPage(
          child: AuthCallbackScreen(),
        ),
      ),

      // Protected routes
      GoRoute(
        path: '/',
        name: 'home',
        pageBuilder: (context, state) => _staticPage(
          title: const Text('Soliplex'),
          body: const HomeScreen(),
          actions: const [_SettingsButton()],
        ),
      ),
      GoRoute(
        path: '/rooms',
        name: 'rooms',
        pageBuilder: (context, state) => _staticPage(
          title: const Text('Rooms'),
          body: const RoomsScreen(),
          actions: const [_SettingsButton()],
        ),
      ),
      GoRoute(
        path: '/rooms/:roomId',
        name: 'room',
        pageBuilder: (context, state) {
          final roomId = state.pathParameters['roomId']!;
          final threadId = state.uri.queryParameters['thread'];
          return NoTransitionPage(
            child: RoomScreen(roomId: roomId, initialThreadId: threadId),
          );
        },
      ),
      // Migration redirect: old thread URLs -> new query param format
      GoRoute(
        path: '/rooms/:roomId/thread/:threadId',
        name: 'thread-redirect',
        redirect: (context, state) {
          final roomId = state.pathParameters['roomId']!;
          final threadId = state.pathParameters['threadId']!;
          return '/rooms/$roomId?thread=$threadId';
        },
      ),
      GoRoute(
        path: '/settings',
        name: 'settings',
        pageBuilder: (context, state) => _staticPage(
          title: const Text('Settings'),
          body: const SettingsScreen(),
        ),
      ),
    ],
    errorBuilder: (context, state) => _staticShell(
      title: const Text('Error'),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const ExcludeSemantics(
              child: Icon(Icons.error_outline, size: 48),
            ),
            const SizedBox(height: 16),
            Text('Page not found: ${state.uri}'),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () => context.go('/'),
              child: const Text('Go Home'),
            ),
          ],
        ),
      ),
    ),
  );
});
