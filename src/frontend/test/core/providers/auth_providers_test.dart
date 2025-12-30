import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/auth_providers.dart';
import 'package:soliplex_frontend/core/state/app_state.dart';

import '../../helpers/auth_test_helpers.dart';

class MockAuthProvider extends Mock implements AuthProvider {}

void main() {
  group('AppStateNotifier', () {
    late ProviderContainer container;
    late AppStateNotifier notifier;

    setUp(() {
      container = ProviderContainer();
      notifier = container.read(appStateProvider.notifier);
    });

    tearDown(() {
      container.dispose();
    });

    test('initial state is NoServer', () {
      final state = container.read(appStateProvider);

      expect(state, isA<AppStateNoServer>());
    });

    group('setNeedsAuth', () {
      test('transitions to NeedsAuth state', () {
        const providers = [testAuthSystem];

        notifier.setNeedsAuth(serverId: 'server1', providers: providers);

        final state = container.read(appStateProvider);
        expect(state, isA<AppStateNeedsAuth>());
        final needsAuth = state as AppStateNeedsAuth;
        expect(needsAuth.serverId, 'server1');
        expect(needsAuth.providers, providers);
      });
    });

    group('beginAuth', () {
      test('transitions to Authenticating state', () {
        notifier.beginAuth('server1', providers: const []);

        final state = container.read(appStateProvider);
        expect(state, isA<AppStateAuthenticating>());
        expect((state as AppStateAuthenticating).serverId, 'server1');
      });
    });

    group('setAuthenticated', () {
      test('transitions to Ready state with config', () {
        notifier.setAuthenticated(serverId: 'server1', config: testSsoConfig);

        final state = container.read(appStateProvider);
        expect(state, isA<AppStateReady>());
        final ready = state as AppStateReady;
        expect(ready.serverId, 'server1');
        expect(ready.config, testSsoConfig);
        expect(ready.user, isNull);
      });

      test('includes user info when provided', () {
        const user = UserInfo(
          id: 'user-123',
          email: 'user@example.com',
          name: 'Test User',
        );

        notifier.setAuthenticated(
          serverId: 'server1',
          config: testSsoConfig,
          user: user,
        );

        final state = container.read(appStateProvider);
        expect(state, isA<AppStateReady>());
        expect((state as AppStateReady).user, user);
      });
    });

    group('setError', () {
      test('transitions to Error state', () {
        notifier.setError(message: 'Auth failed');

        final state = container.read(appStateProvider);
        expect(state, isA<AppStateError>());
        expect((state as AppStateError).message, 'Auth failed');
        expect(state.serverId, isNull);
      });

      test('includes serverId when provided', () {
        notifier.setError(message: 'Auth failed', serverId: 'server1');

        final state = container.read(appStateProvider);
        expect(state, isA<AppStateError>());
        expect((state as AppStateError).serverId, 'server1');
      });

      test('preserves providers from NeedsAuth state', () {
        notifier
          ..setNeedsAuth(serverId: 'server1', providers: [testAuthSystem])
          ..setError(message: 'failed', serverId: 'server1');

        final state = container.read(appStateProvider) as AppStateError;
        expect(state.providers, equals([testAuthSystem]));
      });

      test('preserves providers from Authenticating state', () {
        notifier
          ..beginAuth('server1', providers: [testAuthSystem])
          ..setError(message: 'failed', serverId: 'server1');

        final state = container.read(appStateProvider) as AppStateError;
        expect(state.providers, equals([testAuthSystem]));
      });

      test('preserves providers from prior Error state', () {
        notifier
          ..setNeedsAuth(serverId: 'server1', providers: [testAuthSystem])
          ..setError(message: 'first error', serverId: 'server1')
          ..setError(message: 'second error', serverId: 'server1');

        final state = container.read(appStateProvider) as AppStateError;
        expect(state.message, 'second error');
        expect(state.providers, equals([testAuthSystem]));
      });

      test('returns empty providers from NoServer state', () {
        notifier.setError(message: 'failed');

        final state = container.read(appStateProvider) as AppStateError;
        expect(state.providers, isEmpty);
      });
    });

    group('loggedOut', () {
      test('transitions to NeedsAuth state', () {
        const providers = <OIDCAuthSystem>[];

        // Authenticate then log out
        notifier
          ..beginAuth('server1', providers: providers)
          ..setAuthenticated(serverId: 'server1', config: testSsoConfig)
          ..loggedOut(serverId: 'server1', providers: providers);

        final state = container.read(appStateProvider);
        expect(state, isA<AppStateNeedsAuth>());
        expect((state as AppStateNeedsAuth).serverId, 'server1');
      });
    });

    group('reset', () {
      test('transitions to NoServer state', () {
        notifier
          ..setNeedsAuth(serverId: 'server1', providers: [])
          ..reset();

        final state = container.read(appStateProvider);
        expect(state, isA<AppStateNoServer>());
      });
    });

    group('state transitions', () {
      test('full auth flow', () {
        final states = <AppState>[];
        container.listen(
          appStateProvider,
          (previous, next) => states.add(next),
          fireImmediately: true,
        );

        const providers = [testAuthSystem];
        const user = UserInfo(id: 'user-123');

        notifier
          ..setNeedsAuth(serverId: 'server1', providers: providers)
          ..beginAuth('server1', providers: providers)
          ..setAuthenticated(
            serverId: 'server1',
            config: testSsoConfig,
            user: user,
          );

        expect(states, hasLength(4));
        expect(states[0], isA<AppStateNoServer>());
        expect(states[1], isA<AppStateNeedsAuth>());
        expect(states[2], isA<AppStateAuthenticating>());
        expect(states[3], isA<AppStateReady>());
      });
    });

    group('beginProbe', () {
      test('transitions to Probing state', () {
        notifier.beginProbe('https://api.example.com');

        final state = container.read(appStateProvider);
        expect(state, isA<AppStateProbing>());
        expect(
          (state as AppStateProbing).serverId,
          'https://api.example.com',
        );
      });
    });
  });

  group('createTokenProvider', () {
    late ProviderContainer container;
    late MockAuthProvider mockAuthProvider;

    // Provider to test createTokenProvider via Ref
    final tokenProviderProvider = Provider<TokenProviderFn>(
      createTokenProvider,
    );

    setUp(() {
      mockAuthProvider = MockAuthProvider();
      container = ProviderContainer(
        overrides: [
          authProviderProvider.overrideWithValue(mockAuthProvider),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    test('returns noAuthToken when not in Ready state', () async {
      // Default state is AppStateNoServer
      final tokenProvider = container.read(tokenProviderProvider);

      final token = await tokenProvider();

      expect(token, noAuthToken);
    });

    test('returns noAuthToken for NeedsAuth state', () async {
      container.read(appStateProvider.notifier).setNeedsAuth(
        serverId: 'server1',
        providers: [testAuthSystem],
      );

      final tokenProvider = container.read(tokenProviderProvider);

      final token = await tokenProvider();

      expect(token, noAuthToken);
    });

    test('returns noAuthToken for Authenticating state', () async {
      container
          .read(appStateProvider.notifier)
          .beginAuth('server1', providers: const []);

      final tokenProvider = container.read(tokenProviderProvider);

      final token = await tokenProvider();

      expect(token, noAuthToken);
    });

    test('returns access token when in Ready state', () async {
      container.read(appStateProvider.notifier).setAuthenticated(
            serverId: 'server1',
            config: testSsoConfig,
          );

      final testToken = AuthToken(
        accessToken: 'test-access-token',
        expiresAt: DateTime.now().add(const Duration(hours: 1)),
      );

      when(() => mockAuthProvider.getValidToken('server1', testSsoConfig))
          .thenAnswer((_) async => Authenticated(token: testToken));

      final tokenProvider = container.read(tokenProviderProvider);

      final token = await tokenProvider();

      expect(token, 'test-access-token');
    });

    test('returns noAuthToken for NoToken result', () async {
      container.read(appStateProvider.notifier).setAuthenticated(
            serverId: 'server1',
            config: testSsoConfig,
          );

      when(() => mockAuthProvider.getValidToken('server1', testSsoConfig))
          .thenAnswer((_) async => const NoToken());

      final tokenProvider = container.read(tokenProviderProvider);

      final token = await tokenProvider();

      expect(token, noAuthToken);
    });

    test('returns noAuthToken for TokenExpired result', () async {
      container.read(appStateProvider.notifier).setAuthenticated(
            serverId: 'server1',
            config: testSsoConfig,
          );

      when(() => mockAuthProvider.getValidToken('server1', testSsoConfig))
          .thenAnswer((_) async => const TokenExpired());

      final tokenProvider = container.read(tokenProviderProvider);

      final token = await tokenProvider();

      expect(token, noAuthToken);
    });

    test('returns noAuthToken for RefreshFailed result', () async {
      container.read(appStateProvider.notifier).setAuthenticated(
            serverId: 'server1',
            config: testSsoConfig,
          );

      when(() => mockAuthProvider.getValidToken('server1', testSsoConfig))
          .thenAnswer(
        (_) async => const RefreshFailed(cause: 'Token refresh failed'),
      );

      final tokenProvider = container.read(tokenProviderProvider);

      final token = await tokenProvider();

      expect(token, noAuthToken);
    });

    test('returns noAuthToken for StorageUnavailable result', () async {
      container.read(appStateProvider.notifier).setAuthenticated(
            serverId: 'server1',
            config: testSsoConfig,
          );

      when(() => mockAuthProvider.getValidToken('server1', testSsoConfig))
          .thenAnswer(
        (_) async => const StorageUnavailable(message: 'Keychain locked'),
      );

      final tokenProvider = container.read(tokenProviderProvider);

      final token = await tokenProvider();

      expect(token, noAuthToken);
    });

    test('returns noAuthToken when AuthError is thrown', () async {
      container.read(appStateProvider.notifier).setAuthenticated(
            serverId: 'server1',
            config: testSsoConfig,
          );

      when(() => mockAuthProvider.getValidToken('server1', testSsoConfig))
          .thenThrow(const AuthErrorNetwork(message: 'Network error'));

      final tokenProvider = container.read(tokenProviderProvider);

      final token = await tokenProvider();

      expect(token, noAuthToken);
    });
  });
}
