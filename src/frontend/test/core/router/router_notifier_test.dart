import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/core/providers/auth_providers.dart';
import 'package:soliplex_frontend/core/router/router_notifier.dart';
import 'package:soliplex_frontend/core/state/app_state.dart';

import '../../helpers/auth_test_helpers.dart';

void main() {
  group('RouterNotifier', () {
    late ProviderContainer container;

    test('isAuthenticated returns true when AppStateReady', () {
      container = ProviderContainer(
        overrides: [
          appStateProvider.overrideWith(
            () => TestAppStateNotifier(testAuthenticatedState()),
          ),
        ],
      );
      addTearDown(container.dispose);

      final notifier = container.read(routerNotifierProvider);

      expect(notifier.isAuthenticated, isTrue);
      expect(notifier.isInAuthFlow, isFalse);
    });

    test('isAuthenticated returns false when AppStateNoServer', () {
      container = ProviderContainer(
        overrides: [
          appStateProvider.overrideWith(
            () => TestAppStateNotifier(const AppStateNoServer()),
          ),
        ],
      );
      addTearDown(container.dispose);

      final notifier = container.read(routerNotifierProvider);

      expect(notifier.isAuthenticated, isFalse);
      expect(notifier.isInAuthFlow, isFalse);
    });

    test('isInAuthFlow returns true when AppStateAuthenticating', () {
      container = ProviderContainer(
        overrides: [
          appStateProvider.overrideWith(
            () => TestAppStateNotifier(
              const AppStateAuthenticating(
                serverId: 'http://localhost:8000',
                providers: [],
              ),
            ),
          ),
        ],
      );
      addTearDown(container.dispose);

      final notifier = container.read(routerNotifierProvider);

      expect(notifier.isAuthenticated, isFalse);
      expect(notifier.isInAuthFlow, isTrue);
    });

    test('isInAuthFlow returns true when AppStateProbing', () {
      container = ProviderContainer(
        overrides: [
          appStateProvider.overrideWith(
            () => TestAppStateNotifier(
              const AppStateProbing(serverId: 'http://localhost:8000'),
            ),
          ),
        ],
      );
      addTearDown(container.dispose);

      final notifier = container.read(routerNotifierProvider);

      expect(notifier.isAuthenticated, isFalse);
      expect(notifier.isInAuthFlow, isTrue);
    });

    test('isAuthenticated returns false when AppStateNeedsAuth', () {
      container = ProviderContainer(
        overrides: [
          appStateProvider.overrideWith(
            () => TestAppStateNotifier(
              const AppStateNeedsAuth(
                serverId: 'http://localhost:8000',
                providers: [testAuthSystem],
              ),
            ),
          ),
        ],
      );
      addTearDown(container.dispose);

      final notifier = container.read(routerNotifierProvider);

      expect(notifier.isAuthenticated, isFalse);
      expect(notifier.isInAuthFlow, isFalse);
    });

    test('isAuthenticated returns false when AppStateError', () {
      container = ProviderContainer(
        overrides: [
          appStateProvider.overrideWith(
            () => TestAppStateNotifier(
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
      expect(notifier.isInAuthFlow, isFalse);
    });

    test('state returns current AppState', () {
      container = ProviderContainer(
        overrides: [
          appStateProvider.overrideWith(
            () => TestAppStateNotifier(const AppStateNoServer()),
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
      container.read(routerNotifierProvider).addListener(() => notifyCount++);

      // Trigger state change
      container
          .read(appStateProvider.notifier)
          .beginAuth('http://localhost', providers: const []);

      expect(notifyCount, equals(1));
    });
  });
}
