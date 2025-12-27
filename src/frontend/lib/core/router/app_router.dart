import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:soliplex_frontend/features/home/home_screen.dart';
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

/// Application router configuration.
///
/// Routes:
/// - `/` - Home screen
/// - `/rooms` - List of rooms
/// - `/rooms/:roomId` - Room with thread selection (query param: ?thread=xyz)
/// - `/rooms/:roomId/thread/:threadId` - Redirects to query param format
/// - `/settings` - Settings screen
///
/// All routes use NoTransitionPage for instant navigation.
/// Static screens are wrapped in AppShell via [_staticPage].
/// RoomScreen builds its own AppShell for dynamic configuration.
///
/// AM7: Add auth redirect logic.
final appRouter = GoRouter(
  initialLocation: '/',
  routes: [
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
