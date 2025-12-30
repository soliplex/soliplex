import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/auth/web_auth_provider.dart';
import 'package:soliplex_frontend/core/providers/auth_providers.dart';
import 'package:soliplex_frontend/core/state/app_state.dart';
import 'package:soliplex_frontend/features/login/auth_callback_screen.dart';

import '../../helpers/auth_test_helpers.dart';

class MockWebAuthPendingStorage extends Mock implements WebAuthPendingStorage {}

class MockTokenStorage extends Mock implements TokenStorage {}

class MockOidcDiscoveryService extends Mock implements OidcDiscoveryService {}

class MockAuthProvider extends Mock implements AuthProvider {}

class FakeAuthToken extends Fake implements AuthToken {}

void main() {
  late MockWebAuthPendingStorage mockPendingStorage;
  late MockTokenStorage mockTokenStorage;
  late MockOidcDiscoveryService mockDiscoveryService;
  late MockAuthProvider mockAuthProvider;

  setUpAll(() {
    registerFallbackValue(FakeAuthToken());
  });

  setUp(() {
    mockPendingStorage = MockWebAuthPendingStorage();
    mockTokenStorage = MockTokenStorage();
    mockDiscoveryService = MockOidcDiscoveryService();
    mockAuthProvider = MockAuthProvider();
  });

  Widget createCallbackApp({
    required String callbackPath,
    List<dynamic> overrides = const [],
  }) {
    final router = GoRouter(
      initialLocation: callbackPath,
      routes: [
        GoRoute(
          path: '/auth/callback',
          builder: (context, state) => const AuthCallbackScreen(),
        ),
        GoRoute(
          path: '/login',
          builder: (context, state) => const Scaffold(
            body: Center(child: Text('Login Screen')),
          ),
        ),
        GoRoute(
          path: '/',
          builder: (context, state) => const Scaffold(
            body: Center(child: Text('Home Screen')),
          ),
        ),
      ],
    );

    return ProviderScope(
      overrides: overrides.cast(),
      child: MaterialApp.router(routerConfig: router),
    );
  }

  group('AuthCallbackScreen', () {
    group('validation errors', () {
      testWidgets('shows error and syncs AppState when token missing',
          (tester) async {
        final testNotifier = TestAppStateNotifier(const AppStateNoServer());

        await tester.pumpWidget(
          createCallbackApp(
            callbackPath: '/auth/callback?expires_in=3600',
            overrides: [
              pendingStorageProvider.overrideWithValue(mockPendingStorage),
              appStateProvider.overrideWith(() => testNotifier),
            ],
          ),
        );

        // Wait for callback processing
        await tester.pumpAndSettle();

        expect(find.text('Authentication Failed'), findsOneWidget);
        expect(find.text('Missing access token in callback'), findsOneWidget);
        expect(find.text('Return to login'), findsOneWidget);

        // Verify AppState synced to Error (serverId null for early errors)
        expect(testNotifier.state, isA<AppStateError>());
        final errorState = testNotifier.state as AppStateError;
        expect(errorState.message, 'Missing access token in callback');
        expect(errorState.serverId, isNull);

        // Storage not accessed for validation errors
        verifyNever(() => mockPendingStorage.getPendingAuth());
      });

      testWidgets('shows error when access token is empty', (tester) async {
        await tester.pumpWidget(
          createCallbackApp(
            callbackPath: '/auth/callback?token=&expires_in=3600',
            overrides: [
              pendingStorageProvider.overrideWithValue(mockPendingStorage),
            ],
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('Authentication Failed'), findsOneWidget);
        expect(find.text('Missing access token in callback'), findsOneWidget);

        // Storage not accessed for validation errors
        verifyNever(() => mockPendingStorage.getPendingAuth());
      });

      testWidgets('shows error when expires_in is missing', (tester) async {
        await tester.pumpWidget(
          createCallbackApp(
            callbackPath: '/auth/callback?token=abc123',
            overrides: [
              pendingStorageProvider.overrideWithValue(mockPendingStorage),
            ],
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('Authentication Failed'), findsOneWidget);
        expect(
          find.text('Missing token expiration in callback'),
          findsOneWidget,
        );

        // Storage not accessed for validation errors
        verifyNever(() => mockPendingStorage.getPendingAuth());
      });

      testWidgets('shows error when expires_in is invalid', (tester) async {
        await tester.pumpWidget(
          createCallbackApp(
            callbackPath: '/auth/callback?token=abc123&expires_in=not_a_number',
            overrides: [
              pendingStorageProvider.overrideWithValue(mockPendingStorage),
            ],
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('Authentication Failed'), findsOneWidget);
        expect(find.text('Invalid token expiration format'), findsOneWidget);

        // Storage not accessed for validation errors
        verifyNever(() => mockPendingStorage.getPendingAuth());
      });
    });

    group('pending auth errors', () {
      testWidgets('shows error when no pending auth state', (tester) async {
        when(() => mockPendingStorage.getPendingAuth())
            .thenAnswer((_) async => const NoPendingAuth());

        await tester.pumpWidget(
          createCallbackApp(
            callbackPath: '/auth/callback?token=abc123&expires_in=3600',
            overrides: [
              pendingStorageProvider.overrideWithValue(mockPendingStorage),
            ],
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('Authentication Failed'), findsOneWidget);
        expect(
          find.text('No pending authentication - please try logging in again'),
          findsOneWidget,
        );
      });
    });

    group('discovery errors', () {
      testWidgets('shows error when OIDC discovery fails', (tester) async {
        when(() => mockPendingStorage.getPendingAuth()).thenAnswer(
          (_) async => const PendingAuthFound(
            serverId: 'https://api.example.com',
            authSystem: testAuthSystem,
          ),
        );
        when(() => mockDiscoveryService.discover(testAuthSystem))
            .thenThrow(const AuthErrorConfiguration(message: 'Invalid issuer'));

        await tester.pumpWidget(
          createCallbackApp(
            callbackPath: '/auth/callback?token=abc123&expires_in=3600',
            overrides: [
              pendingStorageProvider.overrideWithValue(mockPendingStorage),
              oidcDiscoveryServiceProvider
                  .overrideWithValue(mockDiscoveryService),
            ],
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('Authentication Failed'), findsOneWidget);
        expect(
          find.text('OIDC discovery failed: Invalid issuer'),
          findsOneWidget,
        );
      });
    });

    group('storage errors', () {
      testWidgets('shows error when token storage fails', (tester) async {
        final testNotifier = TestAppStateNotifier(
          const AppStateAuthenticating(
            serverId: 'https://api.example.com',
            providers: [testAuthSystem],
          ),
        );

        when(() => mockPendingStorage.getPendingAuth()).thenAnswer(
          (_) async => const PendingAuthFound(
            serverId: 'https://api.example.com',
            authSystem: testAuthSystem,
          ),
        );
        when(() => mockDiscoveryService.discover(testAuthSystem))
            .thenAnswer((_) async => testSsoConfig);
        when(() => mockTokenStorage.write(any(), any()))
            .thenThrow(Exception('Keychain locked'));

        await tester.pumpWidget(
          createCallbackApp(
            callbackPath: '/auth/callback?token=abc123&expires_in=3600',
            overrides: [
              pendingStorageProvider.overrideWithValue(mockPendingStorage),
              oidcDiscoveryServiceProvider
                  .overrideWithValue(mockDiscoveryService),
              tokenStorageProvider.overrideWithValue(mockTokenStorage),
              appStateProvider.overrideWith(() => testNotifier),
            ],
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('Authentication Failed'), findsOneWidget);
        expect(
          find.text('Failed to save credentials. Please try again.'),
          findsOneWidget,
        );

        // Verify state transitioned to Error with serverId preserved
        expect(testNotifier.state, isA<AppStateError>());
        final errorState = testNotifier.state as AppStateError;
        expect(errorState.serverId, 'https://api.example.com');
        expect(errorState.providers, [testAuthSystem]);
      });
    });

    group('successful callback', () {
      testWidgets('stores token and transitions to Ready state',
          (tester) async {
        final testNotifier = TestAppStateNotifier(const AppStateNoServer());

        when(() => mockPendingStorage.getPendingAuth()).thenAnswer(
          (_) async => const PendingAuthFound(
            serverId: 'https://api.example.com',
            authSystem: testAuthSystem,
          ),
        );
        when(() => mockDiscoveryService.discover(testAuthSystem))
            .thenAnswer((_) async => testSsoConfig);
        when(() => mockTokenStorage.write(any(), any()))
            .thenAnswer((_) async {});
        when(() => mockPendingStorage.clearPendingAuth())
            .thenAnswer((_) async {});
        when(
          () => mockAuthProvider.getCurrentUser(
            'https://api.example.com',
            testSsoConfig,
          ),
        ).thenAnswer((_) async => testUser);

        await tester.pumpWidget(
          createCallbackApp(
            callbackPath:
                '/auth/callback?token=test-token&expires_in=3600&refresh_token=refresh-123',
            overrides: [
              pendingStorageProvider.overrideWithValue(mockPendingStorage),
              oidcDiscoveryServiceProvider
                  .overrideWithValue(mockDiscoveryService),
              tokenStorageProvider.overrideWithValue(mockTokenStorage),
              authProviderProvider.overrideWithValue(mockAuthProvider),
              appStateProvider.overrideWith(() => testNotifier),
            ],
          ),
        );

        await tester.pumpAndSettle();

        // Verify token was stored
        verify(
          () => mockTokenStorage.write(
            'https://api.example.com',
            any(
              that: isA<AuthToken>()
                  .having((t) => t.accessToken, 'accessToken', 'test-token')
                  .having(
                    (t) => t.refreshToken,
                    'refreshToken',
                    'refresh-123',
                  ),
            ),
          ),
        ).called(1);

        // Verify pending state was cleared
        verify(() => mockPendingStorage.clearPendingAuth()).called(1);

        // Verify state transitioned to Ready with correct values
        expect(testNotifier.state, isA<AppStateReady>());
        final readyState = testNotifier.state as AppStateReady;
        expect(readyState.serverId, 'https://api.example.com');
        expect(readyState.config, testSsoConfig);
        expect(readyState.user, testUser);

        // Should navigate to home
        expect(find.text('Home Screen'), findsOneWidget);
      });

      testWidgets('succeeds despite clearPendingAuth failure', (tester) async {
        final testNotifier = TestAppStateNotifier(const AppStateNoServer());

        when(() => mockPendingStorage.getPendingAuth()).thenAnswer(
          (_) async => const PendingAuthFound(
            serverId: 'https://api.example.com',
            authSystem: testAuthSystem,
          ),
        );
        when(() => mockDiscoveryService.discover(testAuthSystem))
            .thenAnswer((_) async => testSsoConfig);
        when(() => mockTokenStorage.write(any(), any()))
            .thenAnswer((_) async {});
        when(() => mockPendingStorage.clearPendingAuth())
            .thenThrow(Exception('Storage locked'));
        when(
          () => mockAuthProvider.getCurrentUser(
            'https://api.example.com',
            testSsoConfig,
          ),
        ).thenAnswer((_) async => testUser);

        await tester.pumpWidget(
          createCallbackApp(
            callbackPath: '/auth/callback?token=test-token&expires_in=3600',
            overrides: [
              pendingStorageProvider.overrideWithValue(mockPendingStorage),
              oidcDiscoveryServiceProvider
                  .overrideWithValue(mockDiscoveryService),
              tokenStorageProvider.overrideWithValue(mockTokenStorage),
              authProviderProvider.overrideWithValue(mockAuthProvider),
              appStateProvider.overrideWith(() => testNotifier),
            ],
          ),
        );

        await tester.pumpAndSettle();

        // clearPendingAuth was called (and threw)
        verify(() => mockPendingStorage.clearPendingAuth()).called(1);

        // Auth still succeeded despite cleanup failure
        expect(testNotifier.state, isA<AppStateReady>());
        expect(find.text('Home Screen'), findsOneWidget);
      });

      testWidgets('proceeds without user info on failure', (tester) async {
        when(() => mockPendingStorage.getPendingAuth()).thenAnswer(
          (_) async => const PendingAuthFound(
            serverId: 'https://api.example.com',
            authSystem: testAuthSystem,
          ),
        );
        when(() => mockDiscoveryService.discover(testAuthSystem))
            .thenAnswer((_) async => testSsoConfig);
        when(() => mockTokenStorage.write(any(), any()))
            .thenAnswer((_) async {});
        when(() => mockPendingStorage.clearPendingAuth())
            .thenAnswer((_) async {});
        // User info fetch fails
        when(
          () => mockAuthProvider.getCurrentUser(
            'https://api.example.com',
            testSsoConfig,
          ),
        ).thenThrow(const AuthErrorNetwork(message: 'Network error'));

        await tester.pumpWidget(
          createCallbackApp(
            callbackPath: '/auth/callback?token=test-token&expires_in=3600',
            overrides: [
              pendingStorageProvider.overrideWithValue(mockPendingStorage),
              oidcDiscoveryServiceProvider
                  .overrideWithValue(mockDiscoveryService),
              tokenStorageProvider.overrideWithValue(mockTokenStorage),
              authProviderProvider.overrideWithValue(mockAuthProvider),
            ],
          ),
        );

        await tester.pumpAndSettle();

        // Verify token stored with null refreshToken (not in URL)
        verify(
          () => mockTokenStorage.write(
            'https://api.example.com',
            any(
              that: isA<AuthToken>()
                  .having((t) => t.accessToken, 'accessToken', 'test-token')
                  .having((t) => t.refreshToken, 'refreshToken', isNull),
            ),
          ),
        ).called(1);

        // Should still navigate to home despite user info failure
        expect(find.text('Home Screen'), findsOneWidget);
      });
    });

    group('UI states', () {
      testWidgets('shows loading indicator while processing', (tester) async {
        // Use completer to control when the future completes
        final completer = Completer<PendingAuthResult>();
        when(() => mockPendingStorage.getPendingAuth())
            .thenAnswer((_) => completer.future);

        await tester.pumpWidget(
          createCallbackApp(
            callbackPath: '/auth/callback?token=abc&expires_in=3600',
            overrides: [
              pendingStorageProvider.overrideWithValue(mockPendingStorage),
            ],
          ),
        );

        // Use pump() because CircularProgressIndicator animates
        await tester.pump();
        await tester.pump();

        expect(find.byType(CircularProgressIndicator), findsOneWidget);
        expect(find.text('Completing authentication...'), findsOneWidget);

        // Complete the future to clean up
        completer.complete(const NoPendingAuth());
        await tester.pumpAndSettle();
      });

      testWidgets('return to login button navigates to login', (tester) async {
        when(() => mockPendingStorage.getPendingAuth())
            .thenAnswer((_) async => const NoPendingAuth());

        await tester.pumpWidget(
          createCallbackApp(
            callbackPath: '/auth/callback?token=abc&expires_in=3600',
            overrides: [
              pendingStorageProvider.overrideWithValue(mockPendingStorage),
            ],
          ),
        );

        await tester.pumpAndSettle();

        // Tap return to login button
        await tester.tap(find.text('Return to login'));
        await tester.pumpAndSettle();

        expect(find.text('Login Screen'), findsOneWidget);
      });
    });
  });
}
