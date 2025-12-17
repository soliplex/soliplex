import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:soliplex_frontend/features/home/home_screen.dart';
import 'package:soliplex_frontend/features/room/room_screen.dart';
import 'package:soliplex_frontend/features/rooms/rooms_screen.dart';
import 'package:soliplex_frontend/features/settings/settings_screen.dart';
import 'package:soliplex_frontend/features/thread/thread_screen.dart';

/// Application router configuration.
///
/// Routes:
/// - `/` - Home screen with navigation button
/// - `/rooms` - List of rooms
/// - `/rooms/:roomId` - Room detail with threads
/// - `/rooms/:roomId/thread/:threadId` - Thread view (placeholder)
/// - `/settings` - Settings screen
///
/// AM7: Add auth redirect logic.
final appRouter = GoRouter(
  initialLocation: '/',
  routes: [
    GoRoute(
      path: '/',
      name: 'home',
      builder: (context, state) => const HomeScreen(),
    ),
    GoRoute(
      path: '/rooms',
      name: 'rooms',
      builder: (context, state) => const RoomsScreen(),
    ),
    GoRoute(
      path: '/rooms/:roomId',
      name: 'room',
      builder: (context, state) {
        final roomId = state.pathParameters['roomId']!;
        return RoomScreen(roomId: roomId);
      },
    ),
    GoRoute(
      path: '/rooms/:roomId/thread/:threadId',
      name: 'thread',
      builder: (context, state) {
        final roomId = state.pathParameters['roomId']!;
        final threadId = state.pathParameters['threadId']!;
        return ThreadScreen(roomId: roomId, threadId: threadId);
      },
    ),
    GoRoute(
      path: '/settings',
      name: 'settings',
      builder: (context, state) => const SettingsScreen(),
    ),
  ],
  errorBuilder: (context, state) => Scaffold(
    appBar: AppBar(title: const Text('Error')),
    body: Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.error_outline, size: 48),
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
