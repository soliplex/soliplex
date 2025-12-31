import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/auth/oidc_issuer.dart';

void main() {
  group('OidcIssuer', () {
    AuthProviderConfig createConfig({
      String id = 'keycloak',
      String name = 'Keycloak',
      String serverUrl = 'https://idp.example.com/realms/test',
      String clientId = 'my-client',
      String scope = 'openid profile email',
    }) {
      return AuthProviderConfig(
        id: id,
        name: name,
        serverUrl: serverUrl,
        clientId: clientId,
        scope: scope,
      );
    }

    group('property delegation', () {
      test('id delegates to config.id', () {
        final config = createConfig(id: 'test-id');
        final issuer = OidcIssuer.fromConfig(config);

        expect(issuer.id, equals('test-id'));
      });

      test('title delegates to config.name', () {
        final config = createConfig(name: 'Test Provider');
        final issuer = OidcIssuer.fromConfig(config);

        expect(issuer.title, equals('Test Provider'));
      });

      test('serverUrl delegates to config.serverUrl', () {
        final config = createConfig(serverUrl: 'https://auth.example.com');
        final issuer = OidcIssuer.fromConfig(config);

        expect(issuer.serverUrl, equals('https://auth.example.com'));
      });

      test('clientId delegates to config.clientId', () {
        final config = createConfig(clientId: 'my-app');
        final issuer = OidcIssuer.fromConfig(config);

        expect(issuer.clientId, equals('my-app'));
      });

      test('scope delegates to config.scope', () {
        final config = createConfig(scope: 'openid offline_access');
        final issuer = OidcIssuer.fromConfig(config);

        expect(issuer.scope, equals('openid offline_access'));
      });
    });

    group('discoveryUrl', () {
      test('appends well-known path to serverUrl', () {
        final config = createConfig();
        final issuer = OidcIssuer.fromConfig(config);

        expect(
          issuer.discoveryUrl,
          equals(
            'https://idp.example.com/realms/test/.well-known/openid-configuration',
          ),
        );
      });

      test('handles serverUrl without trailing slash', () {
        final config = createConfig(serverUrl: 'https://auth.example.com');
        final issuer = OidcIssuer.fromConfig(config);

        expect(
          issuer.discoveryUrl,
          equals('https://auth.example.com/.well-known/openid-configuration'),
        );
      });
    });

    group('equality', () {
      test('equal when configs are equal', () {
        final config = createConfig();
        final a = OidcIssuer.fromConfig(config);
        final b = OidcIssuer.fromConfig(config);

        expect(a, equals(b));
        expect(a.hashCode, equals(b.hashCode));
      });

      test('equal when configs have same values', () {
        final a = OidcIssuer.fromConfig(createConfig(id: 'same'));
        final b = OidcIssuer.fromConfig(createConfig(id: 'same'));

        expect(a, equals(b));
      });

      test('not equal when configs differ', () {
        final a = OidcIssuer.fromConfig(createConfig(id: 'id-a'));
        final b = OidcIssuer.fromConfig(createConfig(id: 'id-b'));

        expect(a, isNot(equals(b)));
      });
    });
  });
}
