import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/auth_providers.dart';
import 'package:soliplex_frontend/core/state/app_state.dart';

class MockAuthProvider extends Mock implements AuthProvider {}

void main() {
  const testAuthSystem = OIDCAuthSystem(
    id: 'keycloak',
    title: 'Keycloak',
    serverUrl: 'https://auth.example.com',
    clientId: 'client-123',
  );

  const testConfig = SsoConfig(
    authorizationEndpoint: 'https://auth.example.com/authorize',
    tokenEndpoint: 'https://auth.example.com/token',
    authSystem: testAuthSystem,
  );

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
        notifier.beginAuth('server1');

        final state = container.read(appStateProvider);
        expect(state, isA<AppStateAuthenticating>());
        expect((state as AppStateAuthenticating).serverId, 'server1');
      });
    });

    group('setAuthenticated', () {
      test('transitions to Ready state with config', () {
        notifier.setAuthenticated(serverId: 'server1', config: testConfig);

        final state = container.read(appStateProvider);
        expect(state, isA<AppStateReady>());
        final ready = state as AppStateReady;
        expect(ready.serverId, 'server1');
        expect(ready.config, testConfig);
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
          config: testConfig,
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
    });

    group('loggedOut', () {
      test('transitions to NeedsAuth state', () {
        const providers = <OIDCAuthSystem>[];

        // Authenticate then log out
        notifier
          ..beginAuth('server1')
          ..setAuthenticated(serverId: 'server1', config: testConfig)
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
          ..beginAuth('server1')
          ..setAuthenticated(
            serverId: 'server1',
            config: testConfig,
            user: user,
          );

        expect(states, hasLength(4));
        expect(states[0], isA<AppStateNoServer>());
        expect(states[1], isA<AppStateNeedsAuth>());
        expect(states[2], isA<AppStateAuthenticating>());
        expect(states[3], isA<AppStateReady>());
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
      container.read(appStateProvider.notifier).beginAuth('server1');

      final tokenProvider = container.read(tokenProviderProvider);

      final token = await tokenProvider();

      expect(token, noAuthToken);
    });

    test('returns access token when in Ready state', () async {
      container.read(appStateProvider.notifier).setAuthenticated(
            serverId: 'server1',
            config: testConfig,
          );

      final testToken = AuthToken(
        accessToken: 'test-access-token',
        expiresAt: DateTime.now().add(const Duration(hours: 1)),
      );

      when(() => mockAuthProvider.getValidToken('server1', testConfig))
          .thenAnswer((_) async => Authenticated(token: testToken));

      final tokenProvider = container.read(tokenProviderProvider);

      final token = await tokenProvider();

      expect(token, 'test-access-token');
    });

    test('returns noAuthToken for NoToken result', () async {
      container.read(appStateProvider.notifier).setAuthenticated(
            serverId: 'server1',
            config: testConfig,
          );

      when(() => mockAuthProvider.getValidToken('server1', testConfig))
          .thenAnswer((_) async => const NoToken());

      final tokenProvider = container.read(tokenProviderProvider);

      final token = await tokenProvider();

      expect(token, noAuthToken);
    });

    test('returns noAuthToken for TokenExpired result', () async {
      container.read(appStateProvider.notifier).setAuthenticated(
            serverId: 'server1',
            config: testConfig,
          );

      when(() => mockAuthProvider.getValidToken('server1', testConfig))
          .thenAnswer((_) async => const TokenExpired());

      final tokenProvider = container.read(tokenProviderProvider);

      final token = await tokenProvider();

      expect(token, noAuthToken);
    });

    test('returns noAuthToken for RefreshFailed result', () async {
      container.read(appStateProvider.notifier).setAuthenticated(
            serverId: 'server1',
            config: testConfig,
          );

      when(() => mockAuthProvider.getValidToken('server1', testConfig))
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
            config: testConfig,
          );

      when(() => mockAuthProvider.getValidToken('server1', testConfig))
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
            config: testConfig,
          );

      when(() => mockAuthProvider.getValidToken('server1', testConfig))
          .thenThrow(const AuthErrorNetwork(message: 'Network error'));

      final tokenProvider = container.read(tokenProviderProvider);

      final token = await tokenProvider();

      expect(token, noAuthToken);
    });
  });
}
