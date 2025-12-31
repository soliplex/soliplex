import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('AuthProviderConfig', () {
    test('creates with required fields', () {
      const config = AuthProviderConfig(
        id: 'keycloak',
        name: 'Authenticate with Keycloak',
        serverUrl: 'https://sso.example.com/realms/app',
        clientId: 'my-client',
        scope: 'openid email profile',
      );

      expect(config.id, equals('keycloak'));
      expect(config.name, equals('Authenticate with Keycloak'));
      expect(config.serverUrl, equals('https://sso.example.com/realms/app'));
      expect(config.clientId, equals('my-client'));
      expect(config.scope, equals('openid email profile'));
    });

    group('equality', () {
      test('equal when all attributes match', () {
        const config1 = AuthProviderConfig(
          id: 'keycloak',
          name: 'Keycloak',
          serverUrl: 'https://sso.example.com',
          clientId: 'client',
          scope: 'openid',
        );
        const config2 = AuthProviderConfig(
          id: 'keycloak',
          name: 'Keycloak',
          serverUrl: 'https://sso.example.com',
          clientId: 'client',
          scope: 'openid',
        );

        expect(config1, equals(config2));
      });

      test('not equal when id differs', () {
        const config1 = AuthProviderConfig(
          id: 'keycloak',
          name: 'Keycloak',
          serverUrl: 'https://sso.example.com',
          clientId: 'client',
          scope: 'openid',
        );
        const config2 = AuthProviderConfig(
          id: 'other',
          name: 'Keycloak',
          serverUrl: 'https://sso.example.com',
          clientId: 'client',
          scope: 'openid',
        );

        expect(config1, isNot(equals(config2)));
      });

      test('not equal when any attribute differs', () {
        const base = AuthProviderConfig(
          id: 'keycloak',
          name: 'Keycloak',
          serverUrl: 'https://sso.example.com',
          clientId: 'client',
          scope: 'openid',
        );
        const differentName = AuthProviderConfig(
          id: 'keycloak',
          name: 'Different',
          serverUrl: 'https://sso.example.com',
          clientId: 'client',
          scope: 'openid',
        );
        const differentServerUrl = AuthProviderConfig(
          id: 'keycloak',
          name: 'Keycloak',
          serverUrl: 'https://other.example.com',
          clientId: 'client',
          scope: 'openid',
        );
        const differentClientId = AuthProviderConfig(
          id: 'keycloak',
          name: 'Keycloak',
          serverUrl: 'https://sso.example.com',
          clientId: 'other-client',
          scope: 'openid',
        );
        const differentScope = AuthProviderConfig(
          id: 'keycloak',
          name: 'Keycloak',
          serverUrl: 'https://sso.example.com',
          clientId: 'client',
          scope: 'openid profile',
        );

        expect(base, isNot(equals(differentName)));
        expect(base, isNot(equals(differentServerUrl)));
        expect(base, isNot(equals(differentClientId)));
        expect(base, isNot(equals(differentScope)));
      });

      test('identical returns true', () {
        const config = AuthProviderConfig(
          id: 'keycloak',
          name: 'Keycloak',
          serverUrl: 'https://sso.example.com',
          clientId: 'client',
          scope: 'openid',
        );
        expect(config == config, isTrue);
      });
    });

    test('hashCode equal when all attributes match', () {
      const config1 = AuthProviderConfig(
        id: 'keycloak',
        name: 'Keycloak',
        serverUrl: 'https://sso.example.com',
        clientId: 'client',
        scope: 'openid',
      );
      const config2 = AuthProviderConfig(
        id: 'keycloak',
        name: 'Keycloak',
        serverUrl: 'https://sso.example.com',
        clientId: 'client',
        scope: 'openid',
      );

      expect(config1.hashCode, equals(config2.hashCode));
    });

    test('toString includes id and name', () {
      const config = AuthProviderConfig(
        id: 'keycloak',
        name: 'Authenticate with Keycloak',
        serverUrl: 'https://sso.example.com',
        clientId: 'client',
        scope: 'openid',
      );

      final str = config.toString();

      expect(str, contains('keycloak'));
      expect(str, contains('Authenticate with Keycloak'));
    });
  });
}
