import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/auth_providers.dart';
import 'package:soliplex_frontend/core/state/app_state.dart';
import 'package:soliplex_frontend/features/settings/settings_screen.dart';

import '../../helpers/auth_test_helpers.dart';
import '../../helpers/test_helpers.dart';

class MockAuthProvider extends Mock implements AuthProvider {}

class FakeSsoConfig extends Fake implements SsoConfig {}

void main() {
  late MockAuthProvider mockAuthProvider;

  setUpAll(() {
    registerFallbackValue(FakeSsoConfig());
  });

  setUp(() {
    mockAuthProvider = MockAuthProvider();
  });

  group('SettingsScreen', () {
    testWidgets('displays app version', (tester) async {
      await tester.pumpWidget(
        createTestApp(home: const SettingsScreen()),
      );

      expect(find.text('App Version'), findsOneWidget);
      expect(find.textContaining('1.0.0'), findsOneWidget);
    });

    testWidgets('displays backend URL', (tester) async {
      await tester.pumpWidget(
        createTestApp(home: const SettingsScreen()),
      );

      expect(find.text('Backend URL'), findsOneWidget);
      expect(find.text('http://localhost:8000'), findsOneWidget);
    });

    group('when not connected (AppStateNoServer)', () {
      testWidgets('shows not connected message', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(const AppStateNoServer()),
              ),
            ],
          ),
        );

        expect(find.text('Not Connected'), findsOneWidget);
        expect(find.text('No server configured'), findsOneWidget);
        expect(find.byIcon(Icons.cloud_off), findsOneWidget);
      });
    });

    group('when needs auth (AppStateNeedsAuth)', () {
      testWidgets('shows connected but not logged in', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(
                  const AppStateNeedsAuth(
                    serverId: 'https://api.example.com',
                    providers: testProviders,
                  ),
                ),
              ),
            ],
          ),
        );

        expect(find.text('Connected'), findsOneWidget);
        expect(find.text('https://api.example.com'), findsOneWidget);
        expect(find.text('Not logged in'), findsOneWidget);
        expect(find.text('Please log in to continue'), findsOneWidget);
      });
    });

    group('when authenticated (AppStateReady)', () {
      testWidgets('shows server info', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(
                  testAuthenticatedState(serverId: 'https://api.example.com'),
                ),
              ),
            ],
          ),
        );

        expect(find.text('Connected to'), findsOneWidget);
        expect(find.text('https://api.example.com'), findsOneWidget);
        expect(find.byIcon(Icons.cloud_done), findsOneWidget);
      });

      testWidgets('shows user name when available', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(
                  testAuthenticatedState(
                    user: const UserInfo(
                      id: 'user-123',
                      name: 'John Doe',
                      email: 'john@example.com',
                    ),
                  ),
                ),
              ),
            ],
          ),
        );

        expect(find.text('Logged in as'), findsOneWidget);
        expect(find.text('John Doe'), findsOneWidget);
      });

      testWidgets('shows email when name is null', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(
                  testAuthenticatedState(
                    user: const UserInfo(
                      id: 'user-123',
                      email: 'john@example.com',
                    ),
                  ),
                ),
              ),
            ],
          ),
        );

        expect(find.text('Logged in as'), findsOneWidget);
        expect(find.text('john@example.com'), findsOneWidget);
      });

      testWidgets('shows email when name is empty string', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(
                  testAuthenticatedState(
                    user: const UserInfo(
                      id: 'user-123',
                      name: '',
                      email: 'john@example.com',
                    ),
                  ),
                ),
              ),
            ],
          ),
        );

        expect(find.text('Logged in as'), findsOneWidget);
        expect(find.text('john@example.com'), findsOneWidget);
      });

      testWidgets('shows user id when name and email are null',
          (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(
                  testAuthenticatedState(
                    user: const UserInfo(id: 'user-123'),
                  ),
                ),
              ),
            ],
          ),
        );

        expect(find.text('Logged in as'), findsOneWidget);
        expect(find.text('user-123'), findsOneWidget);
      });

      testWidgets('shows user id when name is null and email is empty string',
          (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(
                  testAuthenticatedState(
                    user: const UserInfo(id: 'user-456', email: ''),
                  ),
                ),
              ),
            ],
          ),
        );

        expect(find.text('Logged in as'), findsOneWidget);
        expect(find.text('user-456'), findsOneWidget);
      });

      testWidgets('shows unknown user when user is null', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(
                  testAuthenticatedState(user: null),
                ),
              ),
            ],
          ),
        );

        expect(find.text('Logged in as'), findsOneWidget);
        expect(find.text('Unknown user'), findsOneWidget);
      });

      testWidgets('shows auth provider name', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(testAuthenticatedState()),
              ),
            ],
          ),
        );

        expect(find.text('Auth Provider'), findsOneWidget);
        expect(find.text('Keycloak'), findsOneWidget);
      });

      testWidgets('shows logout button', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(testAuthenticatedState()),
              ),
            ],
          ),
        );

        expect(find.text('Logout'), findsOneWidget);
        expect(find.byIcon(Icons.logout), findsOneWidget);
      });

      testWidgets('logout button shows confirmation dialog', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(testAuthenticatedState()),
              ),
              authProviderProvider.overrideWithValue(mockAuthProvider),
            ],
          ),
        );

        await tester.tap(find.text('Logout'));
        await tester.pumpAndSettle();

        expect(find.text('Are you sure you want to logout?'), findsOneWidget);
        expect(find.text('Cancel'), findsOneWidget);
        // Find the Logout button in the dialog (not the ListTile)
        expect(
          find.widgetWithText(FilledButton, 'Logout'),
          findsOneWidget,
        );
      });

      testWidgets('cancel button dismisses dialog without logout',
          (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(testAuthenticatedState()),
              ),
              authProviderProvider.overrideWithValue(mockAuthProvider),
            ],
          ),
        );

        await tester.tap(find.text('Logout'));
        await tester.pumpAndSettle();

        await tester.tap(find.text('Cancel'));
        await tester.pumpAndSettle();

        // Dialog should be dismissed
        expect(
          find.text('Are you sure you want to logout?'),
          findsNothing,
        );
        // Logout should not be called
        verifyNever(() => mockAuthProvider.logout(any(), any()));
      });

      testWidgets('confirm button calls logout and updates state',
          (tester) async {
        when(() => mockAuthProvider.logout(any(), any()))
            .thenAnswer((_) async {});

        late ProviderContainer container;
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(testAuthenticatedState()),
              ),
              authProviderProvider.overrideWithValue(mockAuthProvider),
            ],
            onContainerCreated: (c) => container = c,
          ),
        );

        await tester.tap(find.text('Logout'));
        await tester.pumpAndSettle();

        // Tap the Logout button in the dialog
        await tester.tap(find.widgetWithText(FilledButton, 'Logout'));
        await tester.pumpAndSettle();

        // Verify logout was called with correct params
        verify(
          () => mockAuthProvider.logout(testServerId, testSsoConfig),
        ).called(1);

        // Verify state transitioned to NeedsAuth with the single provider used
        // for login. Multi-provider servers require re-probing to see all.
        final state = container.read(appStateProvider);
        expect(state, isA<AppStateNeedsAuth>());
        expect((state as AppStateNeedsAuth).serverId, testServerId);
        expect(state.providers, [testAuthSystem]);
      });

      testWidgets('logout error shows snackbar', (tester) async {
        when(() => mockAuthProvider.logout(any(), any()))
            .thenThrow(Exception('Network error'));

        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(testAuthenticatedState()),
              ),
              authProviderProvider.overrideWithValue(mockAuthProvider),
            ],
          ),
        );

        await tester.tap(find.text('Logout'));
        await tester.pumpAndSettle();

        await tester.tap(find.widgetWithText(FilledButton, 'Logout'));
        await tester.pumpAndSettle();

        expect(find.textContaining('Logout failed'), findsOneWidget);
      });
    });

    group('when probing', () {
      testWidgets('shows connecting indicator', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(
                  const AppStateProbing(serverId: 'https://api.example.com'),
                ),
              ),
            ],
          ),
        );

        expect(find.text('Connecting...'), findsOneWidget);
        expect(find.text('https://api.example.com'), findsOneWidget);
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
      });
    });

    group('when authenticating', () {
      testWidgets('shows authenticating indicator', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(
                  const AppStateAuthenticating(
                    serverId: 'https://api.example.com',
                    providers: testProviders,
                  ),
                ),
              ),
            ],
          ),
        );

        expect(find.text('Authenticating...'), findsOneWidget);
        expect(find.text('https://api.example.com'), findsOneWidget);
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
      });
    });

    group('when error', () {
      testWidgets('shows error message', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(
                  const AppStateError(message: 'Connection failed'),
                ),
              ),
            ],
          ),
        );

        expect(find.text('Error'), findsOneWidget);
        expect(find.text('Connection failed'), findsOneWidget);
        expect(find.byIcon(Icons.error_outline), findsOneWidget);
      });

      testWidgets('shows server when available in error state', (tester) async {
        await tester.pumpWidget(
          createTestApp(
            home: const SettingsScreen(),
            overrides: [
              appStateProvider.overrideWith(
                () => TestAppStateNotifier(
                  const AppStateError(
                    message: 'Auth failed',
                    serverId: 'https://api.example.com',
                  ),
                ),
              ),
            ],
          ),
        );

        expect(find.text('Error'), findsOneWidget);
        expect(find.text('Auth failed'), findsOneWidget);
        expect(find.text('Server'), findsOneWidget);
        expect(find.text('https://api.example.com'), findsOneWidget);
      });
    });
  });
}
