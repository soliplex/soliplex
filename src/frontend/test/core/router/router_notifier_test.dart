import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/auth_providers.dart';
import 'package:soliplex_frontend/core/router/router_notifier.dart';
import 'package:soliplex_frontend/core/state/app_state.dart';

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

void main() {
  group('RouterNotifier', () {
    late ProviderContainer container;

    AppStateReady authenticatedState() => const AppStateReady(
          serverId: 'http://localhost:8000',
          config: _testSsoConfig,
          user: _testUser,
        );

    test('isAuthenticated returns true when AppStateReady', () {
      container = ProviderContainer(
        overrides: [
          appStateProvider.overrideWith(
            () => _TestAppStateNotifier(authenticatedState()),
          ),
        ],
      );
      addTearDown(container.dispose);

      final notifier = container.read(routerNotifierProvider);

      expect(notifier.isAuthenticated, isTrue);
      expect(notifier.isAuthenticating, isFalse);
    });

    test('isAuthenticated returns false when AppStateNoServer', () {
      container = ProviderContainer(
        overrides: [
          appStateProvider.overrideWith(
            () => _TestAppStateNotifier(const AppStateNoServer()),
          ),
        ],
      );
      addTearDown(container.dispose);

      final notifier = container.read(routerNotifierProvider);

      expect(notifier.isAuthenticated, isFalse);
      expect(notifier.isAuthenticating, isFalse);
    });

    test('isAuthenticating returns true when AppStateAuthenticating', () {
      container = ProviderContainer(
        overrides: [
          appStateProvider.overrideWith(
            () => _TestAppStateNotifier(
              const AppStateAuthenticating(serverId: 'http://localhost:8000'),
            ),
          ),
        ],
      );
      addTearDown(container.dispose);

      final notifier = container.read(routerNotifierProvider);

      expect(notifier.isAuthenticated, isFalse);
      expect(notifier.isAuthenticating, isTrue);
    });

    test('isAuthenticated returns false when AppStateNeedsAuth', () {
      container = ProviderContainer(
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
      );
      addTearDown(container.dispose);

      final notifier = container.read(routerNotifierProvider);

      expect(notifier.isAuthenticated, isFalse);
      expect(notifier.isAuthenticating, isFalse);
    });

    test('isAuthenticated returns false when AppStateError', () {
      container = ProviderContainer(
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
      );
      addTearDown(container.dispose);

      final notifier = container.read(routerNotifierProvider);

      expect(notifier.isAuthenticated, isFalse);
      expect(notifier.isAuthenticating, isFalse);
    });

    test('state returns current AppState', () {
      container = ProviderContainer(
        overrides: [
          appStateProvider.overrideWith(
            () => _TestAppStateNotifier(const AppStateNoServer()),
          ),
        ],
      );
      addTearDown(container.dispose);

      final notifier = container.read(routerNotifierProvider);

      expect(notifier.state, isA<AppStateNoServer>());
    });

    test('notifies listeners when auth state changes', () {
      container = ProviderContainer();
      addTearDown(container.dispose);

      var notifyCount = 0;
      final notifier = container.read(routerNotifierProvider);
      notifier.addListener(() => notifyCount++);

      // Trigger state change
      container.read(appStateProvider.notifier).beginAuth('http://localhost');

      expect(notifyCount, equals(1));
    });
  });
}
