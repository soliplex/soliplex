import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex/core/auth/secure_sso_storage.dart';
import 'package:soliplex/core/auth/secure_storage_gateway.dart';
import 'package:soliplex/core/auth/sso_config.dart';

class MockSecureStorageGateway extends Mock implements SecureStorageGateway {}

void main() {
  late MockSecureStorageGateway mockStorage;
  late SecureSsoStorage ssoStorage;

  setUp(() {
    mockStorage = MockSecureStorageGateway();
    ssoStorage = SecureSsoStorage(mockStorage);
  });

  group('SecureSsoStorage', () {
    const testServerId = 'server-123';

    group('setSsoConfig', () {
      test('writes all SSO config fields to storage', () async {
        when(() => mockStorage.write(any(), any())).thenAnswer((_) async {});

        final config = SsoConfig(
          id: 'keycloak',
          title: 'Sign in with Keycloak',
          endpoint: 'https://auth.example.com/realms/myrealm',
          tokenEndpoint:
              'https://auth.example.com/realms/myrealm/protocol/openid-connect/token',
          loginUrl: Uri.parse(
            'https://auth.example.com/realms/myrealm/protocol/openid-connect/auth',
          ),
          clientId: 'my-client',
          redirectUrl: 'https://app.example.com/callback',
          scopes: ['openid', 'profile', 'email'],
        );

        await ssoStorage.setSsoConfig(testServerId, config);

        verify(
          () => mockStorage.write('sso.$testServerId.id', 'keycloak'),
        ).called(1);
        verify(
          () => mockStorage.write(
            'sso.$testServerId.title',
            'Sign in with Keycloak',
          ),
        ).called(1);
        verify(
          () => mockStorage.write(
            'sso.$testServerId.endpoint',
            'https://auth.example.com/realms/myrealm',
          ),
        ).called(1);
        verify(
          () => mockStorage.write(
            'sso.$testServerId.tokenEndpoint',
            'https://auth.example.com/realms/myrealm/protocol/openid-connect/token',
          ),
        ).called(1);
        verify(
          () => mockStorage.write(
            'sso.$testServerId.loginUri',
            'https://auth.example.com/realms/myrealm/protocol/openid-connect/auth',
          ),
        ).called(1);
        verify(
          () => mockStorage.write('sso.$testServerId.clientId', 'my-client'),
        ).called(1);
        verify(
          () => mockStorage.write(
            'sso.$testServerId.redirectUrl',
            'https://app.example.com/callback',
          ),
        ).called(1);
        verify(
          () => mockStorage.write(
            'sso.$testServerId.scopes',
            'openid,profile,email',
          ),
        ).called(1);
      });
    });

    group('getSsoConfig', () {
      test('returns SSO config when all fields exist', () async {
        when(
          () => mockStorage.read('sso.$testServerId.id'),
        ).thenAnswer((_) async => 'keycloak');
        when(
          () => mockStorage.read('sso.$testServerId.title'),
        ).thenAnswer((_) async => 'Sign in with Keycloak');
        when(
          () => mockStorage.read('sso.$testServerId.endpoint'),
        ).thenAnswer((_) async => 'https://auth.example.com/realms/myrealm');
        when(
          () => mockStorage.read('sso.$testServerId.tokenEndpoint'),
        ).thenAnswer(
          (_) async =>
              'https://auth.example.com/realms/myrealm/protocol/openid-connect/token',
        );
        when(() => mockStorage.read('sso.$testServerId.loginUri')).thenAnswer(
          (_) async =>
              'https://auth.example.com/realms/myrealm/protocol/openid-connect/auth',
        );
        when(
          () => mockStorage.read('sso.$testServerId.clientId'),
        ).thenAnswer((_) async => 'my-client');
        when(
          () => mockStorage.read('sso.$testServerId.redirectUrl'),
        ).thenAnswer((_) async => 'https://app.example.com/callback');
        when(
          () => mockStorage.read('sso.$testServerId.scopes'),
        ).thenAnswer((_) async => 'openid,profile,email');

        final result = await ssoStorage.getSsoConfig(testServerId);

        expect(result, isNotNull);
        expect(result!.id, equals('keycloak'));
        expect(result.title, equals('Sign in with Keycloak'));
        expect(
          result.endpoint,
          equals('https://auth.example.com/realms/myrealm'),
        );
        expect(
          result.tokenEndpoint,
          equals(
            'https://auth.example.com/realms/myrealm/protocol/openid-connect/token',
          ),
        );
        expect(
          result.loginUrl.toString(),
          equals(
            'https://auth.example.com/realms/myrealm/protocol/openid-connect/auth',
          ),
        );
        expect(result.clientId, equals('my-client'));
        expect(result.redirectUrl, equals('https://app.example.com/callback'));
        expect(result.scopes, equals(['openid', 'profile', 'email']));
      });

      test('returns null when id is missing', () async {
        when(
          () => mockStorage.read('sso.$testServerId.id'),
        ).thenAnswer((_) async => null);
        when(
          () => mockStorage.read('sso.$testServerId.title'),
        ).thenAnswer((_) async => 'title');
        when(
          () => mockStorage.read('sso.$testServerId.endpoint'),
        ).thenAnswer((_) async => 'endpoint');
        when(
          () => mockStorage.read('sso.$testServerId.tokenEndpoint'),
        ).thenAnswer((_) async => 'tokenEndpoint');
        when(
          () => mockStorage.read('sso.$testServerId.loginUri'),
        ).thenAnswer((_) async => 'https://login.example.com');
        when(
          () => mockStorage.read('sso.$testServerId.clientId'),
        ).thenAnswer((_) async => 'clientId');
        when(
          () => mockStorage.read('sso.$testServerId.redirectUrl'),
        ).thenAnswer((_) async => 'redirectUrl');
        when(
          () => mockStorage.read('sso.$testServerId.scopes'),
        ).thenAnswer((_) async => 'openid');

        final result = await ssoStorage.getSsoConfig(testServerId);

        expect(result, isNull);
      });

      test('returns null when any field is missing', () async {
        // Test with all fields null
        when(() => mockStorage.read(any())).thenAnswer((_) async => null);

        final result = await ssoStorage.getSsoConfig(testServerId);

        expect(result, isNull);
      });

      test('correctly splits scopes by comma', () async {
        when(
          () => mockStorage.read('sso.$testServerId.id'),
        ).thenAnswer((_) async => 'keycloak');
        when(
          () => mockStorage.read('sso.$testServerId.title'),
        ).thenAnswer((_) async => 'title');
        when(
          () => mockStorage.read('sso.$testServerId.endpoint'),
        ).thenAnswer((_) async => 'endpoint');
        when(
          () => mockStorage.read('sso.$testServerId.tokenEndpoint'),
        ).thenAnswer((_) async => 'tokenEndpoint');
        when(
          () => mockStorage.read('sso.$testServerId.loginUri'),
        ).thenAnswer((_) async => 'https://login.example.com');
        when(
          () => mockStorage.read('sso.$testServerId.clientId'),
        ).thenAnswer((_) async => 'clientId');
        when(
          () => mockStorage.read('sso.$testServerId.redirectUrl'),
        ).thenAnswer((_) async => 'redirectUrl');
        when(
          () => mockStorage.read('sso.$testServerId.scopes'),
        ).thenAnswer((_) async => 'scope1,scope2,scope3');

        final result = await ssoStorage.getSsoConfig(testServerId);

        expect(result, isNotNull);
        expect(result!.scopes, equals(['scope1', 'scope2', 'scope3']));
      });
    });

    group('deleteSsoConfig', () {
      test('deletes all SSO config fields from storage', () async {
        when(() => mockStorage.delete(any())).thenAnswer((_) async {});

        await ssoStorage.deleteSsoConfig(testServerId);

        verify(() => mockStorage.delete('sso.$testServerId.id')).called(1);
        verify(() => mockStorage.delete('sso.$testServerId.title')).called(1);
        verify(
          () => mockStorage.delete('sso.$testServerId.endpoint'),
        ).called(1);
        verify(
          () => mockStorage.delete('sso.$testServerId.tokenEndpoint'),
        ).called(1);
        verify(
          () => mockStorage.delete('sso.$testServerId.loginUri'),
        ).called(1);
        verify(
          () => mockStorage.delete('sso.$testServerId.clientId'),
        ).called(1);
        verify(
          () => mockStorage.delete('sso.$testServerId.redirectUrl'),
        ).called(1);
        verify(() => mockStorage.delete('sso.$testServerId.scopes')).called(1);
      });
    });

    group('server scoping', () {
      test('uses different keys for different servers', () async {
        when(() => mockStorage.write(any(), any())).thenAnswer((_) async {});

        final config = SsoConfig(
          id: 'keycloak',
          title: 'title',
          endpoint: 'endpoint',
          tokenEndpoint: 'tokenEndpoint',
          loginUrl: Uri.parse('https://login.example.com'),
          clientId: 'clientId',
          redirectUrl: 'redirectUrl',
          scopes: ['openid'],
        );

        await ssoStorage.setSsoConfig('server-a', config);
        await ssoStorage.setSsoConfig('server-b', config);

        verify(() => mockStorage.write('sso.server-a.id', any())).called(1);
        verify(() => mockStorage.write('sso.server-b.id', any())).called(1);
      });
    });
  });
}
