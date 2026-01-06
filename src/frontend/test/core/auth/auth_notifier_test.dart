import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/auth/auth_provider.dart';
import 'package:soliplex_frontend/core/auth/auth_state.dart';

import '../../helpers/test_helpers.dart';

void main() {
  late MockAuthStorage mockStorage;
  late MockTokenRefreshService mockRefreshService;

  setUpAll(() {
    registerFallbackValue(TestData.createAuthenticated());
  });

  setUp(() {
    mockStorage = MockAuthStorage();
    mockRefreshService = MockTokenRefreshService();
  });

  ProviderContainer createContainer() {
    return ProviderContainer(
      overrides: [
        authStorageProvider.overrideWithValue(mockStorage),
        tokenRefreshServiceProvider.overrideWithValue(mockRefreshService),
      ],
    );
  }

  group('AuthNotifier._restoreSession', () {
    group('with expired tokens', () {
      test('attempts refresh before clearing state', () async {
        final expiredTokens = TestData.createAuthenticated(expired: true);

        when(() => mockStorage.loadTokens())
            .thenAnswer((_) async => expiredTokens);
        when(() => mockStorage.clearTokens()).thenAnswer((_) async {});
        when(
          () => mockRefreshService.refresh(
            discoveryUrl: expiredTokens.issuerDiscoveryUrl,
            refreshToken: expiredTokens.refreshToken,
            clientId: expiredTokens.clientId,
          ),
        ).thenAnswer(
          (_) async => const TokenRefreshFailure(
            TokenRefreshFailureReason.invalidGrant,
          ),
        );

        final container = createContainer();
        addTearDown(container.dispose);

        // Read the provider to trigger build() and _restoreSession()
        container.read(authProvider);

        // Wait for async _restoreSession to complete
        await waitForAuthRestore(container);

        // Verify refresh was attempted (stub would fail if wrong params passed)
        verify(
          () => mockRefreshService.refresh(
            discoveryUrl: expiredTokens.issuerDiscoveryUrl,
            refreshToken: expiredTokens.refreshToken,
            clientId: expiredTokens.clientId,
          ),
        ).called(1);
      });

      test('restores session when refresh succeeds', () async {
        final expiredTokens = TestData.createAuthenticated(expired: true);
        final newExpiresAt = DateTime.now().add(const Duration(hours: 1));

        when(() => mockStorage.loadTokens())
            .thenAnswer((_) async => expiredTokens);
        when(() => mockStorage.saveTokens(any())).thenAnswer((_) async {});
        when(
          () => mockRefreshService.refresh(
            discoveryUrl: expiredTokens.issuerDiscoveryUrl,
            refreshToken: expiredTokens.refreshToken,
            clientId: expiredTokens.clientId,
          ),
        ).thenAnswer(
          (_) async => TokenRefreshSuccess(
            accessToken: 'new-access-token',
            refreshToken: 'new-refresh-token',
            expiresAt: newExpiresAt,
            idToken: 'new-id-token',
          ),
        );

        final container = createContainer();
        addTearDown(container.dispose);

        container.read(authProvider);
        await waitForAuthRestore(container);

        final state = container.read(authProvider);
        expect(state, isA<Authenticated>());

        final auth = state as Authenticated;
        expect(auth.accessToken, 'new-access-token');
        expect(auth.refreshToken, 'new-refresh-token');
      });

      test('clears state when refresh fails with invalidGrant', () async {
        final expiredTokens = TestData.createAuthenticated(expired: true);

        when(() => mockStorage.loadTokens())
            .thenAnswer((_) async => expiredTokens);
        when(() => mockStorage.clearTokens()).thenAnswer((_) async {});
        when(
          () => mockRefreshService.refresh(
            discoveryUrl: expiredTokens.issuerDiscoveryUrl,
            refreshToken: expiredTokens.refreshToken,
            clientId: expiredTokens.clientId,
          ),
        ).thenAnswer(
          (_) async => const TokenRefreshFailure(
            TokenRefreshFailureReason.invalidGrant,
          ),
        );

        final container = createContainer();
        addTearDown(container.dispose);

        container.read(authProvider);
        await waitForAuthRestore(container);

        verify(() => mockStorage.clearTokens()).called(1);

        final state = container.read(authProvider);
        expect(state, isA<Unauthenticated>());
      });

      test('clears state when refresh fails with networkError', () async {
        final expiredTokens = TestData.createAuthenticated(expired: true);

        when(() => mockStorage.loadTokens())
            .thenAnswer((_) async => expiredTokens);
        when(() => mockStorage.clearTokens()).thenAnswer((_) async {});
        when(
          () => mockRefreshService.refresh(
            discoveryUrl: expiredTokens.issuerDiscoveryUrl,
            refreshToken: expiredTokens.refreshToken,
            clientId: expiredTokens.clientId,
          ),
        ).thenAnswer(
          (_) async => const TokenRefreshFailure(
            TokenRefreshFailureReason.networkError,
          ),
        );

        final container = createContainer();
        addTearDown(container.dispose);

        container.read(authProvider);
        await waitForAuthRestore(container);

        verify(() => mockStorage.clearTokens()).called(1);

        final state = container.read(authProvider);
        expect(state, isA<Unauthenticated>());
      });

      test('clears state when refresh throws exception', () async {
        final expiredTokens = TestData.createAuthenticated(expired: true);

        when(() => mockStorage.loadTokens())
            .thenAnswer((_) async => expiredTokens);
        when(() => mockStorage.clearTokens()).thenAnswer((_) async {});
        when(
          () => mockRefreshService.refresh(
            discoveryUrl: expiredTokens.issuerDiscoveryUrl,
            refreshToken: expiredTokens.refreshToken,
            clientId: expiredTokens.clientId,
          ),
        ).thenThrow(Exception('Network unavailable'));

        final container = createContainer();
        addTearDown(container.dispose);

        container.read(authProvider);
        await waitForAuthRestore(container);

        verify(() => mockStorage.clearTokens()).called(1);

        final state = container.read(authProvider);
        expect(state, isA<Unauthenticated>());
      });

      // Tests AuthNotifier's handling of noRefreshToken from service.
      // Actual empty-token detection tested in TokenRefreshService tests.
      test('clears state when service reports noRefreshToken', () async {
        final expiredTokensNoRefresh = TestData.createAuthenticated(
          expired: true,
          refreshToken: '',
        );

        when(() => mockStorage.loadTokens())
            .thenAnswer((_) async => expiredTokensNoRefresh);
        when(() => mockStorage.clearTokens()).thenAnswer((_) async {});
        when(
          () => mockRefreshService.refresh(
            discoveryUrl: expiredTokensNoRefresh.issuerDiscoveryUrl,
            refreshToken: '',
            clientId: expiredTokensNoRefresh.clientId,
          ),
        ).thenAnswer(
          (_) async => const TokenRefreshFailure(
            TokenRefreshFailureReason.noRefreshToken,
          ),
        );

        final container = createContainer();
        addTearDown(container.dispose);

        container.read(authProvider);
        await waitForAuthRestore(container);

        // Service is called, AuthNotifier handles the failure
        verify(
          () => mockRefreshService.refresh(
            discoveryUrl: expiredTokensNoRefresh.issuerDiscoveryUrl,
            refreshToken: '',
            clientId: expiredTokensNoRefresh.clientId,
          ),
        ).called(1);

        // Should clear tokens and go unauthenticated
        verify(() => mockStorage.clearTokens()).called(1);

        final state = container.read(authProvider);
        expect(state, isA<Unauthenticated>());
      });
    });

    group('with valid tokens', () {
      test('restores session without refresh attempt', () async {
        final validTokens = TestData.createAuthenticated();

        when(() => mockStorage.loadTokens())
            .thenAnswer((_) async => validTokens);

        final container = createContainer();
        addTearDown(container.dispose);

        container.read(authProvider);
        await waitForAuthRestore(container);

        verifyNever(
          () => mockRefreshService.refresh(
            discoveryUrl: any(named: 'discoveryUrl'),
            refreshToken: any(named: 'refreshToken'),
            clientId: any(named: 'clientId'),
          ),
        );

        final state = container.read(authProvider);
        expect(state, isA<Authenticated>());

        final auth = state as Authenticated;
        expect(auth.accessToken, validTokens.accessToken);
      });
    });

    group('with no stored tokens', () {
      test('transitions to Unauthenticated', () async {
        when(() => mockStorage.loadTokens()).thenAnswer((_) async => null);

        final container = createContainer();
        addTearDown(container.dispose);

        container.read(authProvider);
        await waitForAuthRestore(container);

        final state = container.read(authProvider);
        expect(state, isA<Unauthenticated>());
      });
    });
  });

  // Runtime refresh tests - verify lenient failure handling (preserves session
  // on transient errors, unlike startup which clears on all failures)
  group('AuthNotifier.tryRefresh (runtime)', () {
    late Authenticated validTokens;

    setUp(() {
      validTokens = TestData.createAuthenticated();
    });

    Future<ProviderContainer> setupAuthenticatedSession() async {
      when(() => mockStorage.loadTokens())
          .thenAnswer((_) async => validTokens);

      final container = createContainer()..read(authProvider);
      await waitForAuthRestore(container);

      // Verify we're authenticated before testing tryRefresh
      expect(container.read(authProvider), isA<Authenticated>());

      return container;
    }

    test('preserves session on networkError (lenient)', () async {
      final container = await setupAuthenticatedSession();
      addTearDown(container.dispose);

      when(
        () => mockRefreshService.refresh(
          discoveryUrl: validTokens.issuerDiscoveryUrl,
          refreshToken: validTokens.refreshToken,
          clientId: validTokens.clientId,
        ),
      ).thenAnswer(
        (_) async => const TokenRefreshFailure(
          TokenRefreshFailureReason.networkError,
        ),
      );

      final result =
          await container.read(authProvider.notifier).tryRefresh();

      expect(result, isFalse);
      // Key assertion: session preserved despite failure
      expect(container.read(authProvider), isA<Authenticated>());
      verifyNever(() => mockStorage.clearTokens());
    });

    test('preserves session on noRefreshToken', () async {
      final container = await setupAuthenticatedSession();
      addTearDown(container.dispose);

      when(
        () => mockRefreshService.refresh(
          discoveryUrl: validTokens.issuerDiscoveryUrl,
          refreshToken: validTokens.refreshToken,
          clientId: validTokens.clientId,
        ),
      ).thenAnswer(
        (_) async => const TokenRefreshFailure(
          TokenRefreshFailureReason.noRefreshToken,
        ),
      );

      final result =
          await container.read(authProvider.notifier).tryRefresh();

      expect(result, isFalse);
      // Session preserved - can't refresh but don't destroy existing session
      expect(container.read(authProvider), isA<Authenticated>());
      verifyNever(() => mockStorage.clearTokens());
    });

    test('preserves session on unknownError (optimistic)', () async {
      final container = await setupAuthenticatedSession();
      addTearDown(container.dispose);

      when(
        () => mockRefreshService.refresh(
          discoveryUrl: validTokens.issuerDiscoveryUrl,
          refreshToken: validTokens.refreshToken,
          clientId: validTokens.clientId,
        ),
      ).thenAnswer(
        (_) async => const TokenRefreshFailure(
          TokenRefreshFailureReason.unknownError,
        ),
      );

      final result =
          await container.read(authProvider.notifier).tryRefresh();

      expect(result, isFalse);
      // Session preserved - unknown errors treated optimistically
      expect(container.read(authProvider), isA<Authenticated>());
      verifyNever(() => mockStorage.clearTokens());
    });

    test('clears state only on invalidGrant (definitive rejection)', () async {
      final container = await setupAuthenticatedSession();
      addTearDown(container.dispose);

      when(
        () => mockRefreshService.refresh(
          discoveryUrl: validTokens.issuerDiscoveryUrl,
          refreshToken: validTokens.refreshToken,
          clientId: validTokens.clientId,
        ),
      ).thenAnswer(
        (_) async => const TokenRefreshFailure(
          TokenRefreshFailureReason.invalidGrant,
        ),
      );
      when(() => mockStorage.clearTokens()).thenAnswer((_) async {});

      final result =
          await container.read(authProvider.notifier).tryRefresh();

      expect(result, isFalse);
      // Key assertion: only invalidGrant triggers logout
      expect(container.read(authProvider), isA<Unauthenticated>());
      verify(() => mockStorage.clearTokens()).called(1);
    });

    test('updates tokens on success', () async {
      final container = await setupAuthenticatedSession();
      addTearDown(container.dispose);

      final newExpiresAt = DateTime.now().add(const Duration(hours: 2));

      when(
        () => mockRefreshService.refresh(
          discoveryUrl: validTokens.issuerDiscoveryUrl,
          refreshToken: validTokens.refreshToken,
          clientId: validTokens.clientId,
        ),
      ).thenAnswer(
        (_) async => TokenRefreshSuccess(
          accessToken: 'new-access-token',
          refreshToken: 'new-refresh-token',
          expiresAt: newExpiresAt,
          idToken: 'new-id-token',
        ),
      );
      when(() => mockStorage.saveTokens(any())).thenAnswer((_) async {});

      final result =
          await container.read(authProvider.notifier).tryRefresh();

      expect(result, isTrue);

      final state = container.read(authProvider);
      expect(state, isA<Authenticated>());

      final auth = state as Authenticated;
      expect(auth.accessToken, 'new-access-token');
      expect(auth.refreshToken, 'new-refresh-token');
    });

    test('continues to Authenticated when storage save throws', () async {
      final container = await setupAuthenticatedSession();
      addTearDown(container.dispose);

      final newExpiresAt = DateTime.now().add(const Duration(hours: 2));

      when(
        () => mockRefreshService.refresh(
          discoveryUrl: validTokens.issuerDiscoveryUrl,
          refreshToken: validTokens.refreshToken,
          clientId: validTokens.clientId,
        ),
      ).thenAnswer(
        (_) async => TokenRefreshSuccess(
          accessToken: 'new-access-token',
          refreshToken: 'new-refresh-token',
          expiresAt: newExpiresAt,
          idToken: 'new-id-token',
        ),
      );
      // Storage throws - simulates keychain locked, full disk, etc.
      when(() => mockStorage.saveTokens(any()))
          .thenThrow(Exception('Keychain locked'));

      final result =
          await container.read(authProvider.notifier).tryRefresh();

      // Key assertion: refresh succeeds despite storage failure
      // Session works for current app run, just won't survive restart
      expect(result, isTrue);

      final state = container.read(authProvider);
      expect(state, isA<Authenticated>());

      final auth = state as Authenticated;
      expect(auth.accessToken, 'new-access-token');
    });

    test('returns false when not authenticated', () async {
      when(() => mockStorage.loadTokens()).thenAnswer((_) async => null);

      final container = createContainer();
      addTearDown(container.dispose);

      container.read(authProvider);
      await waitForAuthRestore(container);

      expect(container.read(authProvider), isA<Unauthenticated>());

      final result =
          await container.read(authProvider.notifier).tryRefresh();

      expect(result, isFalse);
      // No refresh attempted when not authenticated
      verifyNever(
        () => mockRefreshService.refresh(
          discoveryUrl: any(named: 'discoveryUrl'),
          refreshToken: any(named: 'refreshToken'),
          clientId: any(named: 'clientId'),
        ),
      );
    });
  });
}
