import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/core/router/app_router.dart';
import 'package:soliplex_frontend/features/home/home_screen.dart';
import 'package:soliplex_frontend/features/room/room_screen.dart';
import 'package:soliplex_frontend/features/rooms/rooms_screen.dart';
import 'package:soliplex_frontend/features/settings/settings_screen.dart';
import 'package:soliplex_frontend/features/thread/thread_screen.dart';

Widget createRouterApp() {
  return ProviderScope(
    child: MaterialApp.router(
      routerConfig: appRouter,
    ),
  );
}

void main() {
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
      await tester.pumpWidget(createRouterApp());

      await tester.pumpAndSettle();

      unawaited(appRouter.push('/rooms/general'));
      await tester.pumpAndSettle();

      expect(find.byType(RoomScreen), findsOneWidget);
    });

    testWidgets('navigates to thread screen with parameters', (tester) async {
      await tester.pumpWidget(createRouterApp());

      await tester.pumpAndSettle();

      unawaited(appRouter.push('/rooms/general/thread/thread-1'));
      await tester.pumpAndSettle();

      expect(find.byType(ThreadScreen), findsOneWidget);
    });

    testWidgets('navigates to settings screen', (tester) async {
      await tester.pumpWidget(createRouterApp());

      await tester.pumpAndSettle();

      unawaited(appRouter.push('/settings'));
      await tester.pumpAndSettle();

      expect(find.byType(SettingsScreen), findsOneWidget);
    });

    testWidgets('shows error page for unknown route', (tester) async {
      await tester.pumpWidget(createRouterApp());

      await tester.pumpAndSettle();

      unawaited(appRouter.push('/unknown-route'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Page not found'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('error page has go home button', (tester) async {
      await tester.pumpWidget(createRouterApp());

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
