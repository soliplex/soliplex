import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/auth_providers.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';
import 'package:soliplex_frontend/core/router/app_router.dart';
import 'package:soliplex_frontend/core/state/app_state.dart';
import 'package:soliplex_frontend/features/home/home_screen.dart';
import 'package:soliplex_frontend/features/login/auth_callback_screen.dart';
import 'package:soliplex_frontend/features/login/login_screen.dart';
import 'package:soliplex_frontend/features/room/room_screen.dart';
import 'package:soliplex_frontend/features/rooms/rooms_screen.dart';
import 'package:soliplex_frontend/features/settings/settings_screen.dart';

// TODO(auth): Extract to test/helpers/auth_test_helpers.dart if duplicated again.
/// Test notifier that starts in a specific state.
class _TestAppStateNotifier extends AppStateNotifier {
  _TestAppStateNotifier(this._initialState);
  final AppState _initialState;

  @override
  AppState build() => _initialState;
}

const _testAuthSystem = OIDCAuthSystem(
  id: 'test',
  title: 'Test',
  serverUrl: 'https://auth.example.com',
  clientId: 'test-client',
);

const _testSsoConfig = SsoConfig(
  authSystem: _testAuthSystem,
  authorizationEndpoint: 'https://auth.example.com/authorize',
  tokenEndpoint: 'https://auth.example.com/token',
);

const _testUser = UserInfo(
  id: 'test-user-id',
  email: 'test@example.com',
);

/// Test app that provides access to the router for navigation.
class _TestApp extends ConsumerStatefulWidget {
  const _TestApp({this.initialLocation});

  final String? initialLocation;

  @override
  ConsumerState<_TestApp> createState() => _TestAppState();
}

class _TestAppState extends ConsumerState<_TestApp> {
  late final GoRouter _router = ref.read(routerProvider);
  bool _navigated = false;

  @override
  Widget build(BuildContext context) {
    final router = _router;

    // Set initial location if specified (only once)
    final initialLocation = widget.initialLocation;
    if (initialLocation != null && !_navigated) {
      _navigated = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        router.go(initialLocation);
      });
    }

    return MaterialApp.router(routerConfig: router);
  }
}

/// Creates a test app with the router provider.
Widget createRouterApp({
  List<dynamic> overrides = const [],
  String? initialLocation,
}) {
  return ProviderScope(
    overrides: overrides.cast(),
    child: _TestApp(initialLocation: initialLocation),
  );
}

/// Authenticated state for tests.
AppStateReady _authenticatedState() {
  return const AppStateReady(
    serverId: 'http://localhost:8000',
    config: _testSsoConfig,
    user: _testUser,
  );
}

/// Common overrides for authenticated tests.
List<dynamic> authenticatedOverrides() {
  return [
    appStateProvider.overrideWith(
      () => _TestAppStateNotifier(_authenticatedState()),
    ),
    // Override rooms provider to avoid async loading
    roomsProvider.overrideWith((ref) async => const []),
  ];
}

/// Common overrides for tests that navigate to RoomScreen.
List<dynamic> roomScreenOverrides(String roomId) {
  return [
    ...authenticatedOverrides(),
    threadsProvider(roomId).overrideWith((ref) async => []),
    lastViewedThreadProvider(roomId)
        .overrideWith((ref) async => const NoLastViewed()),
  ];
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('AppRouter - Authentication', () {
    testWidgets('redirects to login when AppStateNoServer', (tester) async {
      await tester.pumpWidget(
        createRouterApp(
          overrides: [
            appStateProvider.overrideWith(
              () => _TestAppStateNotifier(const AppStateNoServer()),
            ),
          ],
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byType(LoginScreen), findsOneWidget);
    });

    testWidgets('redirects to login when AppStateNeedsAuth', (tester) async {
      await tester.pumpWidget(
        createRouterApp(
          overrides: [
            appStateProvider.overrideWith(
              () => _TestAppStateNotifier(
                const AppStateNeedsAuth(
                  serverId: 'http://localhost:8000',
                  providers: [_testAuthSystem],
                ),
              ),
            ),
          ],
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byType(LoginScreen), findsOneWidget);
    });

    testWidgets('redirects to login when AppStateError', (tester) async {
      await tester.pumpWidget(
        createRouterApp(
          overrides: [
            appStateProvider.overrideWith(
              () => _TestAppStateNotifier(
                const AppStateError(
                  message: 'Auth failed',
                  serverId: 'http://localhost:8000',
                ),
              ),
            ),
          ],
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byType(LoginScreen), findsOneWidget);
    });

    testWidgets('shows home when authenticated', (tester) async {
      await tester.pumpWidget(
        createRouterApp(overrides: authenticatedOverrides()),
      );

      await tester.pumpAndSettle();

      expect(find.byType(HomeScreen), findsOneWidget);
    });

    testWidgets('redirects from login to home when already authenticated',
        (tester) async {
      await tester.pumpWidget(
        createRouterApp(
          overrides: authenticatedOverrides(),
          initialLocation: '/login',
        ),
      );

      // Pump multiple times to allow redirect
      await tester.pump();
      await tester.pump();
      await tester.pumpAndSettle();

      expect(find.byType(HomeScreen), findsOneWidget);
      expect(find.byType(LoginScreen), findsNothing);
    });

    testWidgets('allows auth callback route during authentication',
        (tester) async {
      await tester.pumpWidget(
        createRouterApp(
          overrides: [
            appStateProvider.overrideWith(
              () => _TestAppStateNotifier(
                const AppStateAuthenticating(serverId: 'http://localhost:8000'),
              ),
            ),
          ],
          initialLocation: '/auth/callback',
        ),
      );

      // Pump to process navigation, don't settle due to spinner
      await tester.pump();
      await tester.pump();
      await tester.pump();

      expect(find.byType(AuthCallbackScreen), findsOneWidget);
    });

    testWidgets('preserves return URL in login redirect', (tester) async {
      await tester.pumpWidget(
        createRouterApp(
          overrides: [
            appStateProvider.overrideWith(
              () => _TestAppStateNotifier(const AppStateNoServer()),
            ),
            threadsProvider('test-room').overrideWith((ref) async => []),
            lastViewedThreadProvider('test-room')
                .overrideWith((ref) async => const NoLastViewed()),
          ],
          initialLocation: '/rooms/test-room',
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byType(LoginScreen), findsOneWidget);
    });

    testWidgets('redirects to valid relative path from login', (tester) async {
      await tester.pumpWidget(
        createRouterApp(
          overrides: [
            ...authenticatedOverrides(),
            threadsProvider('general').overrideWith((ref) async => []),
            lastViewedThreadProvider('general')
                .overrideWith((ref) async => const NoLastViewed()),
          ],
          initialLocation: '/login?from=%2Frooms%2Fgeneral',
        ),
      );

      // Pump to process navigation and redirect
      await tester.pump();
      await tester.pump();
      await tester.pump();

      expect(find.byType(RoomScreen), findsOneWidget);
    });

    testWidgets('blocks protocol-relative URL in from param (open redirect)',
        (tester) async {
      await tester.pumpWidget(
        createRouterApp(
          overrides: authenticatedOverrides(),
          // Encoded //evil.com/phish
          initialLocation: '/login?from=%2F%2Fevil.com%2Fphish',
        ),
      );

      await tester.pump();
      await tester.pump();
      await tester.pumpAndSettle();

      // Should redirect to home, not external site
      expect(find.byType(HomeScreen), findsOneWidget);
    });

    testWidgets('blocks absolute URL in from param (open redirect)',
        (tester) async {
      await tester.pumpWidget(
        createRouterApp(
          overrides: authenticatedOverrides(),
          // Encoded https://evil.com/phish
          initialLocation: '/login?from=https%3A%2F%2Fevil.com%2Fphish',
        ),
      );

      await tester.pump();
      await tester.pump();
      await tester.pumpAndSettle();

      // Should redirect to home, not external site
      expect(find.byType(HomeScreen), findsOneWidget);
    });
  });

  group('AppRouter - Navigation', () {
    testWidgets('navigates to home screen at /', (tester) async {
      await tester.pumpWidget(
        createRouterApp(overrides: authenticatedOverrides()),
      );

      await tester.pumpAndSettle();

      expect(find.byType(HomeScreen), findsOneWidget);
    });

    testWidgets('navigates to rooms screen', (tester) async {
      await tester.pumpWidget(
        createRouterApp(
          overrides: authenticatedOverrides(),
          initialLocation: '/rooms',
        ),
      );

      // Pump to process navigation and async loading
      await tester.pump();
      await tester.pump();
      await tester.pumpAndSettle();

      expect(find.byType(RoomsScreen), findsOneWidget);
    });

    testWidgets('navigates to room screen with roomId', (tester) async {
      await tester.pumpWidget(
        createRouterApp(
          overrides: roomScreenOverrides('general'),
          initialLocation: '/rooms/general',
        ),
      );

      // Pump to process navigation
      await tester.pump();
      await tester.pump();
      await tester.pump();

      expect(find.byType(RoomScreen), findsOneWidget);
    });

    testWidgets('redirects old thread URL to query param format',
        (tester) async {
      await tester.pumpWidget(
        createRouterApp(
          overrides: roomScreenOverrides('general'),
          initialLocation: '/rooms/general/thread/thread-1',
        ),
      );

      // Pump to process navigation and redirect
      await tester.pump();
      await tester.pump();
      await tester.pump();

      // Should show RoomScreen (redirect target)
      expect(find.byType(RoomScreen), findsOneWidget);
    });

    testWidgets('passes thread query param to RoomScreen', (tester) async {
      await tester.pumpWidget(
        createRouterApp(
          overrides: roomScreenOverrides('general'),
          initialLocation: '/rooms/general?thread=thread-123',
        ),
      );

      // Pump to process navigation
      await tester.pump();
      await tester.pump();
      await tester.pump();

      final roomScreen = tester.widget<RoomScreen>(find.byType(RoomScreen));
      expect(roomScreen.initialThreadId, equals('thread-123'));
    });

    testWidgets('RoomScreen receives null when no thread query param',
        (tester) async {
      await tester.pumpWidget(
        createRouterApp(
          overrides: roomScreenOverrides('general'),
          initialLocation: '/rooms/general',
        ),
      );

      // Pump to process navigation
      await tester.pump();
      await tester.pump();
      await tester.pump();

      final roomScreen = tester.widget<RoomScreen>(find.byType(RoomScreen));
      expect(roomScreen.initialThreadId, isNull);
    });

    testWidgets('navigates to settings screen', (tester) async {
      await tester.pumpWidget(
        createRouterApp(
          overrides: authenticatedOverrides(),
          initialLocation: '/settings',
        ),
      );

      // Pump to process navigation
      await tester.pump();
      await tester.pump();
      await tester.pumpAndSettle();

      expect(find.byType(SettingsScreen), findsOneWidget);
    });

    testWidgets('shows error page for unknown route', (tester) async {
      await tester.pumpWidget(
        createRouterApp(
          overrides: authenticatedOverrides(),
          initialLocation: '/unknown-route',
        ),
      );

      // Pump to process navigation
      await tester.pump();
      await tester.pump();
      await tester.pumpAndSettle();

      expect(find.textContaining('Page not found'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('error page has go home button', (tester) async {
      await tester.pumpWidget(
        createRouterApp(
          overrides: authenticatedOverrides(),
          initialLocation: '/invalid',
        ),
      );

      // Pump to process navigation
      await tester.pump();
      await tester.pump();
      await tester.pumpAndSettle();

      expect(find.text('Go Home'), findsOneWidget);

      await tester.tap(find.text('Go Home'));
      await tester.pumpAndSettle();

      expect(find.byType(HomeScreen), findsOneWidget);
    });
  });
}
