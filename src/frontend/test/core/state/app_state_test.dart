import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/state/app_state.dart';

void main() {
  group('AppState', () {
    group('AppStateNoServer', () {
      test('creates instance', () {
        const state = AppStateNoServer();

        expect(state, isA<AppState>());
        expect(state, isA<AppStateNoServer>());
      });

      test('equality works correctly', () {
        const state1 = AppStateNoServer();
        const state2 = AppStateNoServer();

        expect(state1, equals(state2));
        expect(state1.hashCode, equals(state2.hashCode));
      });

      test('toString returns expected format', () {
        const state = AppStateNoServer();

        expect(state.toString(), equals('AppStateNoServer()'));
      });
    });

    group('AppStateNeedsAuth', () {
      test('creates with required fields', () {
        const providers = [
          OIDCAuthSystem(
            id: 'keycloak',
            title: 'Keycloak',
            serverUrl: 'https://auth.example.com',
            clientId: 'client-123',
          ),
        ];

        const state = AppStateNeedsAuth(
          serverId: 'server1',
          providers: providers,
        );

        expect(state.serverId, equals('server1'));
        expect(state.providers, equals(providers));
      });

      test('equality works correctly', () {
        const providers = [
          OIDCAuthSystem(
            id: 'keycloak',
            title: 'Keycloak',
            serverUrl: 'https://auth.example.com',
            clientId: 'client-123',
          ),
        ];

        const state1 = AppStateNeedsAuth(
          serverId: 'server1',
          providers: providers,
        );
        const state2 = AppStateNeedsAuth(
          serverId: 'server1',
          providers: providers,
        );

        expect(state1, equals(state2));
        expect(state1.hashCode, equals(state2.hashCode));
      });

      test('equality works with different list instances same content', () {
        // Use non-const to create different list instances
        final state1 = AppStateNeedsAuth(
          serverId: 'server1',
          providers: [
            const OIDCAuthSystem(
              id: 'keycloak',
              title: 'Keycloak',
              serverUrl: 'https://auth.example.com',
              clientId: 'client-123',
            ),
          ],
        );
        final state2 = AppStateNeedsAuth(
          serverId: 'server1',
          providers: [
            const OIDCAuthSystem(
              id: 'keycloak',
              title: 'Keycloak',
              serverUrl: 'https://auth.example.com',
              clientId: 'client-123',
            ),
          ],
        );

        expect(state1, equals(state2));
        expect(state1.hashCode, equals(state2.hashCode));
      });

      test('not equal with different serverId', () {
        const providers = <OIDCAuthSystem>[];

        const state1 = AppStateNeedsAuth(
          serverId: 'server1',
          providers: providers,
        );
        const state2 = AppStateNeedsAuth(
          serverId: 'server2',
          providers: providers,
        );

        expect(state1, isNot(equals(state2)));
      });

      test('not equal with different providers', () {
        const state1 = AppStateNeedsAuth(
          serverId: 'server1',
          providers: [
            OIDCAuthSystem(
              id: 'keycloak',
              title: 'Keycloak',
              serverUrl: 'https://auth.example.com',
              clientId: 'client-123',
            ),
          ],
        );
        const state2 = AppStateNeedsAuth(
          serverId: 'server1',
          providers: [],
        );

        expect(state1, isNot(equals(state2)));
      });

      test('toString returns expected format', () {
        const state = AppStateNeedsAuth(
          serverId: 'server1',
          providers: [
            OIDCAuthSystem(
              id: 'keycloak',
              title: 'Keycloak',
              serverUrl: 'https://auth.example.com',
              clientId: 'client-123',
            ),
          ],
        );

        expect(
          state.toString(),
          equals('AppStateNeedsAuth(serverId: server1, providers: 1)'),
        );
      });
    });

    group('AppStateAuthenticating', () {
      test('creates with serverId', () {
        const state = AppStateAuthenticating(serverId: 'server1');

        expect(state.serverId, equals('server1'));
      });

      test('equality works correctly', () {
        const state1 = AppStateAuthenticating(serverId: 'server1');
        const state2 = AppStateAuthenticating(serverId: 'server1');

        expect(state1, equals(state2));
        expect(state1.hashCode, equals(state2.hashCode));
      });

      test('not equal with different serverId', () {
        const state1 = AppStateAuthenticating(serverId: 'server1');
        const state2 = AppStateAuthenticating(serverId: 'server2');

        expect(state1, isNot(equals(state2)));
      });

      test('toString returns expected format', () {
        const state = AppStateAuthenticating(serverId: 'server1');

        expect(
          state.toString(),
          equals('AppStateAuthenticating(serverId: server1)'),
        );
      });
    });

    group('AppStateReady', () {
      test('creates with required fields', () {
        const state = AppStateReady(serverId: 'server1');

        expect(state.serverId, equals('server1'));
        expect(state.user, isNull);
      });

      test('creates with user info', () {
        const user = UserInfo(
          id: 'user-123',
          email: 'user@example.com',
          name: 'Test User',
        );

        const state = AppStateReady(
          serverId: 'server1',
          user: user,
        );

        expect(state.serverId, equals('server1'));
        expect(state.user, equals(user));
      });

      test('equality works correctly', () {
        const user = UserInfo(id: 'user-123');

        const state1 = AppStateReady(serverId: 'server1', user: user);
        const state2 = AppStateReady(serverId: 'server1', user: user);

        expect(state1, equals(state2));
        expect(state1.hashCode, equals(state2.hashCode));
      });

      test('not equal with different serverId', () {
        const state1 = AppStateReady(serverId: 'server1');
        const state2 = AppStateReady(serverId: 'server2');

        expect(state1, isNot(equals(state2)));
      });

      test('not equal with different user', () {
        const state1 = AppStateReady(
          serverId: 'server1',
          user: UserInfo(id: 'user-1'),
        );
        const state2 = AppStateReady(
          serverId: 'server1',
          user: UserInfo(id: 'user-2'),
        );

        expect(state1, isNot(equals(state2)));
      });

      test('toString returns expected format without user', () {
        const state = AppStateReady(serverId: 'server1');

        expect(
          state.toString(),
          equals('AppStateReady(serverId: server1, user: null)'),
        );
      });

      test('toString returns expected format with user', () {
        const state = AppStateReady(
          serverId: 'server1',
          user: UserInfo(id: 'user-123'),
        );

        expect(state.toString(), contains('server1'));
        expect(state.toString(), contains('user-123'));
      });
    });

    group('AppStateError', () {
      test('creates with message only', () {
        const state = AppStateError(message: 'Something went wrong');

        expect(state.message, equals('Something went wrong'));
        expect(state.serverId, isNull);
      });

      test('creates with message and serverId', () {
        const state = AppStateError(
          message: 'Auth failed',
          serverId: 'server1',
        );

        expect(state.message, equals('Auth failed'));
        expect(state.serverId, equals('server1'));
      });

      test('equality works correctly', () {
        const state1 = AppStateError(message: 'Error', serverId: 'server1');
        const state2 = AppStateError(message: 'Error', serverId: 'server1');

        expect(state1, equals(state2));
        expect(state1.hashCode, equals(state2.hashCode));
      });

      test('not equal with different message', () {
        const state1 = AppStateError(message: 'Error 1');
        const state2 = AppStateError(message: 'Error 2');

        expect(state1, isNot(equals(state2)));
      });

      test('not equal with different serverId', () {
        const state1 = AppStateError(message: 'Error', serverId: 'server1');
        const state2 = AppStateError(message: 'Error', serverId: 'server2');

        expect(state1, isNot(equals(state2)));
      });

      test('toString returns expected format without serverId', () {
        const state = AppStateError(message: 'Something went wrong');

        expect(
          state.toString(),
          equals('AppStateError(message: Something went wrong)'),
        );
      });

      test('toString returns expected format with serverId', () {
        const state = AppStateError(
          message: 'Auth failed',
          serverId: 'server1',
        );

        expect(
          state.toString(),
          equals('AppStateError(message: Auth failed, serverId: server1)'),
        );
      });
    });

    group('sealed class exhaustiveness', () {
      test('can pattern match on all variants', () {
        final states = <AppState>[
          const AppStateNoServer(),
          const AppStateNeedsAuth(serverId: 'server1', providers: []),
          const AppStateAuthenticating(serverId: 'server1'),
          const AppStateReady(serverId: 'server1'),
          const AppStateError(message: 'error'),
        ];

        for (final state in states) {
          final description = switch (state) {
            AppStateNoServer() => 'no_server',
            AppStateNeedsAuth(:final serverId) => 'needs_auth: $serverId',
            AppStateAuthenticating(:final serverId) =>
              'authenticating: $serverId',
            AppStateReady(:final serverId, :final user) =>
              'ready: $serverId, user: $user',
            AppStateError(:final message) => 'error: $message',
          };
          expect(description, isNotEmpty);
        }
      });
    });
  });
}
