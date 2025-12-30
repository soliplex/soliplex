import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/state/app_state.dart';

import '../../helpers/auth_test_helpers.dart';

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

    group('AppStateProbing', () {
      test('creates with serverId', () {
        const state = AppStateProbing(serverId: 'https://api.example.com');

        expect(state.serverId, equals('https://api.example.com'));
      });

      test('equality works correctly', () {
        const state1 = AppStateProbing(serverId: 'https://api.example.com');
        const state2 = AppStateProbing(serverId: 'https://api.example.com');

        expect(state1, equals(state2));
        expect(state1.hashCode, equals(state2.hashCode));
      });

      test('not equal with different serverId', () {
        const state1 = AppStateProbing(serverId: 'https://api1.example.com');
        const state2 = AppStateProbing(serverId: 'https://api2.example.com');

        expect(state1, isNot(equals(state2)));
      });

      test('toString returns expected format', () {
        const state = AppStateProbing(serverId: 'https://api.example.com');

        expect(
          state.toString(),
          equals('AppStateProbing(serverId: https://api.example.com)'),
        );
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

      test('equality works with different list instances', () {
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
          providers: [
            OIDCAuthSystem(
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
      test('creates with serverId and providers', () {
        const state = AppStateAuthenticating(
          serverId: 'server1',
          providers: [testAuthSystem],
        );

        expect(state.serverId, equals('server1'));
        expect(state.providers, equals([testAuthSystem]));
      });

      test('equality works correctly', () {
        const state1 = AppStateAuthenticating(
          serverId: 'server1',
          providers: [testAuthSystem],
        );
        const state2 = AppStateAuthenticating(
          serverId: 'server1',
          providers: [testAuthSystem],
        );

        expect(state1, equals(state2));
        expect(state1.hashCode, equals(state2.hashCode));
      });

      test('not equal with different serverId', () {
        const state1 = AppStateAuthenticating(
          serverId: 'server1',
          providers: [],
        );
        const state2 = AppStateAuthenticating(
          serverId: 'server2',
          providers: [],
        );

        expect(state1, isNot(equals(state2)));
      });

      test('not equal with different providers', () {
        const state1 = AppStateAuthenticating(
          serverId: 'server1',
          providers: [testAuthSystem],
        );
        const state2 = AppStateAuthenticating(
          serverId: 'server1',
          providers: [],
        );

        expect(state1, isNot(equals(state2)));
      });

      test('toString returns expected format', () {
        const state = AppStateAuthenticating(
          serverId: 'server1',
          providers: [],
        );

        expect(
          state.toString(),
          equals('AppStateAuthenticating(serverId: server1)'),
        );
      });
    });

    group('AppStateReady', () {
      test('creates with required fields', () {
        const state = AppStateReady(serverId: 'server1', config: testSsoConfig);

        expect(state.serverId, equals('server1'));
        expect(state.config, equals(testSsoConfig));
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
          config: testSsoConfig,
          user: user,
        );

        expect(state.serverId, equals('server1'));
        expect(state.config, equals(testSsoConfig));
        expect(state.user, equals(user));
      });

      test('equality works correctly', () {
        const user = UserInfo(id: 'user-123');

        const state1 = AppStateReady(
          serverId: 'server1',
          config: testSsoConfig,
          user: user,
        );
        const state2 = AppStateReady(
          serverId: 'server1',
          config: testSsoConfig,
          user: user,
        );

        expect(state1, equals(state2));
        expect(state1.hashCode, equals(state2.hashCode));
      });

      test('not equal with different serverId', () {
        const state1 =
            AppStateReady(serverId: 'server1', config: testSsoConfig);
        const state2 =
            AppStateReady(serverId: 'server2', config: testSsoConfig);

        expect(state1, isNot(equals(state2)));
      });

      test('not equal with different config', () {
        const otherConfig = SsoConfig(
          authorizationEndpoint: 'https://other.example.com/authorize',
          tokenEndpoint: 'https://other.example.com/token',
          authSystem: testAuthSystem,
        );

        const state1 =
            AppStateReady(serverId: 'server1', config: testSsoConfig);
        const state2 = AppStateReady(serverId: 'server1', config: otherConfig);

        expect(state1, isNot(equals(state2)));
      });

      test('not equal with different user', () {
        const state1 = AppStateReady(
          serverId: 'server1',
          config: testSsoConfig,
          user: UserInfo(id: 'user-1'),
        );
        const state2 = AppStateReady(
          serverId: 'server1',
          config: testSsoConfig,
          user: UserInfo(id: 'user-2'),
        );

        expect(state1, isNot(equals(state2)));
      });

      test('toString returns expected format without user', () {
        const state = AppStateReady(serverId: 'server1', config: testSsoConfig);

        expect(state.toString(), contains('server1'));
        expect(state.toString(), contains('user: null'));
      });

      test('toString returns expected format with user', () {
        const state = AppStateReady(
          serverId: 'server1',
          config: testSsoConfig,
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
          const AppStateProbing(serverId: 'server1'),
          const AppStateNeedsAuth(serverId: 'server1', providers: []),
          const AppStateAuthenticating(serverId: 'server1', providers: []),
          const AppStateReady(serverId: 'server1', config: testSsoConfig),
          const AppStateError(message: 'error'),
        ];

        for (final state in states) {
          final description = switch (state) {
            AppStateNoServer() => 'no_server',
            AppStateProbing(:final serverId) => 'probing: $serverId',
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
