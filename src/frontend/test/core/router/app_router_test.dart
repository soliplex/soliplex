import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';
import 'package:soliplex_frontend/core/router/app_router.dart';
import 'package:soliplex_frontend/features/home/home_screen.dart';
import 'package:soliplex_frontend/features/room/room_screen.dart';
import 'package:soliplex_frontend/features/rooms/rooms_screen.dart';
import 'package:soliplex_frontend/features/settings/settings_screen.dart';

// Using dynamic list since Override type is internal in Riverpod 3.0
Widget createRouterApp({List<dynamic> overrides = const []}) {
  return ProviderScope(
    overrides: overrides.cast(),
    child: MaterialApp.router(
      routerConfig: appRouter,
    ),
  );
}

/// Common overrides for tests that navigate to RoomScreen.
List<dynamic> roomScreenOverrides(String roomId) {
  return [
    threadsProvider(roomId).overrideWith((ref) async => []),
    lastViewedThreadProvider(roomId)
        .overrideWith((ref) async => const NoLastViewed()),
  ];
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('AppRouter', () {
    testWidgets('navigates to home screen at /', (tester) async {
      await tester.pumpWidget(createRouterApp());

      await tester.pumpAndSettle();

      expect(find.byType(HomeScreen), findsOneWidget);
    });

    testWidgets('navigates to rooms screen', (tester) async {
      await tester.pumpWidget(createRouterApp());

      await tester.pumpAndSettle();

      unawaited(appRouter.push('/rooms'));
      await tester.pumpAndSettle();

      expect(find.byType(RoomsScreen), findsOneWidget);
    });

    testWidgets('navigates to room screen with roomId', (tester) async {
      await tester.pumpWidget(
        createRouterApp(overrides: roomScreenOverrides('general')),
      );

      await tester.pumpAndSettle();

      unawaited(appRouter.push('/rooms/general'));
      await tester.pumpAndSettle();

      expect(find.byType(RoomScreen), findsOneWidget);
    });

    testWidgets('redirects old thread URL to query param format',
        (tester) async {
      await tester.pumpWidget(
        createRouterApp(overrides: roomScreenOverrides('general')),
      );

      await tester.pumpAndSettle();

      // Old format: /rooms/:roomId/thread/:threadId
      // Should redirect to: /rooms/:roomId?thread=:threadId
      unawaited(appRouter.push('/rooms/general/thread/thread-1'));
      await tester.pumpAndSettle();

      // Should show RoomScreen (redirect target)
      expect(find.byType(RoomScreen), findsOneWidget);
    });

    testWidgets('passes thread query param to RoomScreen', (tester) async {
      await tester.pumpWidget(
        createRouterApp(overrides: roomScreenOverrides('general')),
      );

      await tester.pumpAndSettle();

      unawaited(appRouter.push('/rooms/general?thread=thread-123'));
      await tester.pumpAndSettle();

      final roomScreen = tester.widget<RoomScreen>(find.byType(RoomScreen));
      expect(roomScreen.initialThreadId, equals('thread-123'));
    });

    testWidgets('RoomScreen receives null when no thread query param',
        (tester) async {
      await tester.pumpWidget(
        createRouterApp(overrides: roomScreenOverrides('general')),
      );

      await tester.pumpAndSettle();

      unawaited(appRouter.push('/rooms/general'));
      await tester.pumpAndSettle();

      final roomScreen = tester.widget<RoomScreen>(find.byType(RoomScreen));
      expect(roomScreen.initialThreadId, isNull);
    });

    testWidgets('navigates to settings screen', (tester) async {
      // Override providers to prevent async init issues from prior navigation
      await tester.pumpWidget(
        createRouterApp(overrides: roomScreenOverrides('general')),
      );

      await tester.pumpAndSettle();

      unawaited(appRouter.push('/settings'));
      await tester.pumpAndSettle();

      expect(find.byType(SettingsScreen), findsOneWidget);
    });

    testWidgets('shows error page for unknown route', (tester) async {
      await tester.pumpWidget(
        createRouterApp(overrides: roomScreenOverrides('general')),
      );

      await tester.pumpAndSettle();

      unawaited(appRouter.push('/unknown-route'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Page not found'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('error page has go home button', (tester) async {
      await tester.pumpWidget(
        createRouterApp(overrides: roomScreenOverrides('general')),
      );

      await tester.pumpAndSettle();

      unawaited(appRouter.push('/invalid'));
      await tester.pumpAndSettle();

      expect(find.text('Go Home'), findsOneWidget);

      await tester.tap(find.text('Go Home'));
      await tester.pumpAndSettle();

      expect(find.byType(HomeScreen), findsOneWidget);
    });
  });
}
