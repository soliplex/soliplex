import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('OIDCAuthSystem', () {
    test('creates with required fields', () {
      const system = OIDCAuthSystem(
        id: 'google',
        title: 'Google',
        serverUrl: 'https://accounts.google.com',
        clientId: 'client-123',
      );

      expect(system.id, equals('google'));
      expect(system.title, equals('Google'));
      expect(system.serverUrl, equals('https://accounts.google.com'));
      expect(system.clientId, equals('client-123'));
      expect(system.scope, equals('openid profile email'));
    });

    test('creates with custom scope', () {
      const system = OIDCAuthSystem(
        id: 'keycloak',
        title: 'Keycloak',
        serverUrl: 'https://keycloak.example.com/realms/app',
        clientId: 'my-app',
        scope: 'openid profile email groups',
      );

      expect(system.scope, equals('openid profile email groups'));
    });

    group('copyWith', () {
      test('creates modified copy', () {
        const system = OIDCAuthSystem(
          id: 'google',
          title: 'Google',
          serverUrl: 'https://accounts.google.com',
          clientId: 'client-123',
        );
        final modified = system.copyWith(title: 'Google SSO');

        expect(modified.id, equals('google'));
        expect(modified.title, equals('Google SSO'));
        expect(system.title, equals('Google'));
      });

      test('creates copy with all fields modified', () {
        const system = OIDCAuthSystem(
          id: 'google',
          title: 'Google',
          serverUrl: 'https://accounts.google.com',
          clientId: 'client-123',
        );
        final modified = system.copyWith(
          id: 'keycloak',
          title: 'Keycloak',
          serverUrl: 'https://keycloak.example.com',
          clientId: 'new-client',
          scope: 'openid groups',
        );

        expect(modified.id, equals('keycloak'));
        expect(modified.title, equals('Keycloak'));
        expect(modified.serverUrl, equals('https://keycloak.example.com'));
        expect(modified.clientId, equals('new-client'));
        expect(modified.scope, equals('openid groups'));
      });
    });

    group('equality', () {
      test('equal when all fields match', () {
        const system1 = OIDCAuthSystem(
          id: 'google',
          title: 'Google',
          serverUrl: 'https://accounts.google.com',
          clientId: 'client-123',
        );
        const system2 = OIDCAuthSystem(
          id: 'google',
          title: 'Google',
          serverUrl: 'https://accounts.google.com',
          clientId: 'client-123',
        );

        expect(system1, equals(system2));
      });

      test('not equal when fields differ', () {
        const system1 = OIDCAuthSystem(
          id: 'google',
          title: 'Google',
          serverUrl: 'https://accounts.google.com',
          clientId: 'client-123',
        );
        const system2 = OIDCAuthSystem(
          id: 'google',
          title: 'Different Title',
          serverUrl: 'https://accounts.google.com',
          clientId: 'client-123',
        );
        const system3 = OIDCAuthSystem(
          id: 'keycloak',
          title: 'Google',
          serverUrl: 'https://accounts.google.com',
          clientId: 'client-123',
        );

        expect(system1, isNot(equals(system2)));
        expect(system1, isNot(equals(system3)));
      });
    });

    test('hashCode consistent with equality', () {
      const system1 = OIDCAuthSystem(
        id: 'google',
        title: 'Google',
        serverUrl: 'https://accounts.google.com',
        clientId: 'client-123',
      );
      const system2 = OIDCAuthSystem(
        id: 'google',
        title: 'Google',
        serverUrl: 'https://accounts.google.com',
        clientId: 'client-123',
      );

      expect(system1.hashCode, equals(system2.hashCode));
    });

    test('toString includes id and title', () {
      const system = OIDCAuthSystem(
        id: 'google',
        title: 'Google SSO',
        serverUrl: 'https://accounts.google.com',
        clientId: 'client-123',
      );

      final str = system.toString();

      expect(str, contains('google'));
      expect(str, contains('Google SSO'));
    });

    group('JSON serialization', () {
      test('toJson converts to map', () {
        const system = OIDCAuthSystem(
          id: 'google',
          title: 'Google',
          serverUrl: 'https://accounts.google.com',
          clientId: 'client-123',
          scope: 'openid profile',
        );

        final json = system.toJson();

        expect(json['id'], equals('google'));
        expect(json['title'], equals('Google'));
        expect(json['server_url'], equals('https://accounts.google.com'));
        expect(json['client_id'], equals('client-123'));
        expect(json['scope'], equals('openid profile'));
      });

      test('fromJson parses map', () {
        final json = {
          'id': 'google',
          'title': 'Google',
          'server_url': 'https://accounts.google.com',
          'client_id': 'client-123',
          'scope': 'openid profile email',
        };

        final system = OIDCAuthSystem.fromJson(json);

        expect(system.id, equals('google'));
        expect(system.title, equals('Google'));
        expect(system.serverUrl, equals('https://accounts.google.com'));
        expect(system.clientId, equals('client-123'));
        expect(system.scope, equals('openid profile email'));
      });

      test('fromJson uses default scope when missing', () {
        final json = {
          'id': 'google',
          'title': 'Google',
          'server_url': 'https://accounts.google.com',
          'client_id': 'client-123',
        };

        final system = OIDCAuthSystem.fromJson(json);

        expect(system.scope, equals('openid profile email'));
      });

      test('roundtrip preserves data', () {
        const original = OIDCAuthSystem(
          id: 'google',
          title: 'Google',
          serverUrl: 'https://accounts.google.com',
          clientId: 'client-123',
          scope: 'openid profile email groups',
        );

        final restored = OIDCAuthSystem.fromJson(original.toJson());

        expect(restored.id, equals(original.id));
        expect(restored.title, equals(original.title));
        expect(restored.serverUrl, equals(original.serverUrl));
        expect(restored.clientId, equals(original.clientId));
        expect(restored.scope, equals(original.scope));
      });
    });
  });
}
