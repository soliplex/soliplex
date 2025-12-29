import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('SsoConfig', () {
    const authSystem = OIDCAuthSystem(
      id: 'google',
      title: 'Google',
      serverUrl: 'https://accounts.google.com',
      clientId: 'client-123',
    );

    test('creates with required fields', () {
      const config = SsoConfig(
        authSystem: authSystem,
        authorizationEndpoint: 'https://accounts.google.com/o/oauth2/v2/auth',
        tokenEndpoint: 'https://oauth2.googleapis.com/token',
      );

      expect(config.authSystem, equals(authSystem));
      expect(
        config.authorizationEndpoint,
        equals('https://accounts.google.com/o/oauth2/v2/auth'),
      );
      expect(
        config.tokenEndpoint,
        equals('https://oauth2.googleapis.com/token'),
      );
      expect(config.endSessionEndpoint, isNull);
      expect(config.userInfoEndpoint, isNull);
    });

    test('creates with all fields', () {
      const config = SsoConfig(
        authSystem: authSystem,
        authorizationEndpoint: 'https://accounts.google.com/o/oauth2/v2/auth',
        tokenEndpoint: 'https://oauth2.googleapis.com/token',
        endSessionEndpoint: 'https://accounts.google.com/logout',
        userInfoEndpoint: 'https://openidconnect.googleapis.com/v1/userinfo',
      );

      expect(
        config.endSessionEndpoint,
        equals('https://accounts.google.com/logout'),
      );
      expect(
        config.userInfoEndpoint,
        equals('https://openidconnect.googleapis.com/v1/userinfo'),
      );
    });

    test('id delegates to authSystem', () {
      const config = SsoConfig(
        authSystem: authSystem,
        authorizationEndpoint: 'https://accounts.google.com/o/oauth2/v2/auth',
        tokenEndpoint: 'https://oauth2.googleapis.com/token',
      );

      expect(config.id, equals('google'));
    });

    test('clientId delegates to authSystem', () {
      const config = SsoConfig(
        authSystem: authSystem,
        authorizationEndpoint: 'https://accounts.google.com/o/oauth2/v2/auth',
        tokenEndpoint: 'https://oauth2.googleapis.com/token',
      );

      expect(config.clientId, equals('client-123'));
    });

    test('scope delegates to authSystem', () {
      const config = SsoConfig(
        authSystem: authSystem,
        authorizationEndpoint: 'https://accounts.google.com/o/oauth2/v2/auth',
        tokenEndpoint: 'https://oauth2.googleapis.com/token',
      );

      expect(config.scope, equals('openid profile email'));
    });

    group('copyWith', () {
      test('creates modified copy', () {
        const config = SsoConfig(
          authSystem: authSystem,
          authorizationEndpoint: 'https://accounts.google.com/o/oauth2/v2/auth',
          tokenEndpoint: 'https://oauth2.googleapis.com/token',
        );
        final modified =
            config.copyWith(endSessionEndpoint: 'https://logout.example.com');

        expect(
          modified.endSessionEndpoint,
          equals('https://logout.example.com'),
        );
        expect(config.endSessionEndpoint, isNull);
      });
    });

    group('equality', () {
      test('equal when all fields match', () {
        const config1 = SsoConfig(
          authSystem: authSystem,
          authorizationEndpoint: 'https://google.com/auth',
          tokenEndpoint: 'https://google.com/token',
        );
        const config2 = SsoConfig(
          authSystem: authSystem,
          authorizationEndpoint: 'https://google.com/auth',
          tokenEndpoint: 'https://google.com/token',
        );

        expect(config1, equals(config2));
      });

      test('not equal when fields differ', () {
        const config1 = SsoConfig(
          authSystem: authSystem,
          authorizationEndpoint: 'https://one.com/auth',
          tokenEndpoint: 'https://one.com/token',
        );
        const config2 = SsoConfig(
          authSystem: authSystem,
          authorizationEndpoint: 'https://two.com/auth',
          tokenEndpoint: 'https://two.com/token',
        );
        const otherSystem = OIDCAuthSystem(
          id: 'keycloak',
          title: 'Keycloak',
          serverUrl: 'https://keycloak.example.com',
          clientId: 'other-client',
        );
        const config3 = SsoConfig(
          authSystem: otherSystem,
          authorizationEndpoint: 'https://one.com/auth',
          tokenEndpoint: 'https://one.com/token',
        );

        expect(config1, isNot(equals(config2)));
        expect(config1, isNot(equals(config3)));
      });
    });

    test('hashCode consistent with equality', () {
      const config1 = SsoConfig(
        authSystem: authSystem,
        authorizationEndpoint: 'https://google.com/auth',
        tokenEndpoint: 'https://google.com/token',
      );
      const config2 = SsoConfig(
        authSystem: authSystem,
        authorizationEndpoint: 'https://google.com/auth',
        tokenEndpoint: 'https://google.com/token',
      );

      expect(config1.hashCode, equals(config2.hashCode));
    });

    test('toString includes id', () {
      const config = SsoConfig(
        authSystem: authSystem,
        authorizationEndpoint: 'https://accounts.google.com/o/oauth2/v2/auth',
        tokenEndpoint: 'https://oauth2.googleapis.com/token',
      );

      expect(config.toString(), contains('google'));
    });

    group('JSON serialization', () {
      test('toJson converts to map', () {
        const config = SsoConfig(
          authSystem: authSystem,
          authorizationEndpoint: 'https://accounts.google.com/o/oauth2/v2/auth',
          tokenEndpoint: 'https://oauth2.googleapis.com/token',
          endSessionEndpoint: 'https://accounts.google.com/logout',
          userInfoEndpoint: 'https://openidconnect.googleapis.com/v1/userinfo',
        );

        final json = config.toJson();

        expect(json['auth_system'], isA<Map<String, dynamic>>());
        expect(
          json['authorization_endpoint'],
          equals('https://accounts.google.com/o/oauth2/v2/auth'),
        );
        expect(
          json['token_endpoint'],
          equals('https://oauth2.googleapis.com/token'),
        );
        expect(
          json['end_session_endpoint'],
          equals('https://accounts.google.com/logout'),
        );
        expect(
          json['userinfo_endpoint'],
          equals('https://openidconnect.googleapis.com/v1/userinfo'),
        );
      });

      test('fromJson parses map', () {
        final json = {
          'auth_system': {
            'id': 'google',
            'title': 'Google',
            'server_url': 'https://accounts.google.com',
            'client_id': 'client-123',
            'scope': 'openid profile email',
          },
          'authorization_endpoint':
              'https://accounts.google.com/o/oauth2/v2/auth',
          'token_endpoint': 'https://oauth2.googleapis.com/token',
          'end_session_endpoint': 'https://accounts.google.com/logout',
          'userinfo_endpoint':
              'https://openidconnect.googleapis.com/v1/userinfo',
        };

        final config = SsoConfig.fromJson(json);

        expect(config.authSystem.id, equals('google'));
        expect(
          config.authorizationEndpoint,
          equals('https://accounts.google.com/o/oauth2/v2/auth'),
        );
        expect(
          config.tokenEndpoint,
          equals('https://oauth2.googleapis.com/token'),
        );
        expect(
          config.endSessionEndpoint,
          equals('https://accounts.google.com/logout'),
        );
        expect(
          config.userInfoEndpoint,
          equals('https://openidconnect.googleapis.com/v1/userinfo'),
        );
      });

      test('fromJson handles minimal fields', () {
        final json = {
          'auth_system': {
            'id': 'google',
            'title': 'Google',
            'server_url': 'https://accounts.google.com',
            'client_id': 'client-123',
          },
          'authorization_endpoint':
              'https://accounts.google.com/o/oauth2/v2/auth',
          'token_endpoint': 'https://oauth2.googleapis.com/token',
        };

        final config = SsoConfig.fromJson(json);

        expect(config.endSessionEndpoint, isNull);
        expect(config.userInfoEndpoint, isNull);
      });

      test('roundtrip preserves data', () {
        const original = SsoConfig(
          authSystem: authSystem,
          authorizationEndpoint: 'https://accounts.google.com/o/oauth2/v2/auth',
          tokenEndpoint: 'https://oauth2.googleapis.com/token',
          endSessionEndpoint: 'https://accounts.google.com/logout',
          userInfoEndpoint: 'https://openidconnect.googleapis.com/v1/userinfo',
        );

        final restored = SsoConfig.fromJson(original.toJson());

        expect(restored.authSystem.id, equals(original.authSystem.id));
        expect(
          restored.authorizationEndpoint,
          equals(original.authorizationEndpoint),
        );
        expect(restored.tokenEndpoint, equals(original.tokenEndpoint));
        expect(
          restored.endSessionEndpoint,
          equals(original.endSessionEndpoint),
        );
        expect(restored.userInfoEndpoint, equals(original.userInfoEndpoint));
      });
    });
  });
}
