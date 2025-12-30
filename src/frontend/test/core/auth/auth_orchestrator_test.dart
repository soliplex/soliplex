import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/auth/auth_orchestrator.dart';

import '../../helpers/auth_test_helpers.dart';

class MockAuthApi extends Mock implements AuthApi {}

class MockOidcDiscoveryService extends Mock implements OidcDiscoveryService {}

class MockAuthProvider extends Mock implements AuthProvider {}

void main() {
  late MockAuthApi mockAuthApi;
  late MockOidcDiscoveryService mockDiscoveryService;
  late MockAuthProvider mockAuthProvider;
  late AuthOrchestrator orchestrator;

  setUpAll(() {
    registerFallbackValue(testAuthSystem);
    registerFallbackValue(testSsoConfig);
  });

  setUp(() {
    mockAuthApi = MockAuthApi();
    mockDiscoveryService = MockOidcDiscoveryService();
    mockAuthProvider = MockAuthProvider();

    orchestrator = AuthOrchestrator(
      authApi: mockAuthApi,
      discoveryService: mockDiscoveryService,
      authProvider: mockAuthProvider,
    );
  });

  group('AuthOrchestrator.probeServer', () {
    test('returns ProbeSuccess when providers are available', () async {
      when(() => mockAuthApi.getAuthProviders('https://api.example.com'))
          .thenAnswer((_) async => testProviders);

      final result = await orchestrator.probeServer('https://api.example.com');

      expect(result, isA<ProbeSuccess>());
      final success = result as ProbeSuccess;
      expect(success.providers, equals(testProviders));
    });

    test('returns ProbeFailure when no providers available', () async {
      when(() => mockAuthApi.getAuthProviders('https://api.example.com'))
          .thenAnswer((_) async => []);

      final result = await orchestrator.probeServer('https://api.example.com');

      expect(result, isA<ProbeFailure>());
      final failure = result as ProbeFailure;
      expect(failure.message, contains('No authentication providers'));
    });

    test('returns ProbeFailure on ApiException', () async {
      when(() => mockAuthApi.getAuthProviders('https://api.example.com'))
          .thenThrow(
        const ApiException(statusCode: 500, message: 'Server error'),
      );

      final result = await orchestrator.probeServer('https://api.example.com');

      expect(result, isA<ProbeFailure>());
      final failure = result as ProbeFailure;
      expect(failure.message, equals('Server error'));
    });

    test('returns ProbeFailure on ClientException', () async {
      when(() => mockAuthApi.getAuthProviders('https://api.example.com'))
          .thenThrow(http.ClientException('Connection refused'));

      final result = await orchestrator.probeServer('https://api.example.com');

      expect(result, isA<ProbeFailure>());
      final failure = result as ProbeFailure;
      expect(failure.message, contains('Connection failed'));
    });

    test('returns ProbeFailure on FormatException', () async {
      when(() => mockAuthApi.getAuthProviders('https://api.example.com'))
          .thenThrow(const FormatException('Invalid JSON'));

      final result = await orchestrator.probeServer('https://api.example.com');

      expect(result, isA<ProbeFailure>());
      final failure = result as ProbeFailure;
      expect(failure.message, equals('Invalid server response'));
    });

    test('returns ProbeFailure on generic Exception', () async {
      when(() => mockAuthApi.getAuthProviders('https://api.example.com'))
          .thenThrow(Exception('Unknown error'));

      final result = await orchestrator.probeServer('https://api.example.com');

      expect(result, isA<ProbeFailure>());
      final failure = result as ProbeFailure;
      expect(failure.message, contains('Unknown error'));
    });
  });

  group('AuthOrchestrator.login', () {
    setUp(() {
      // Default mock for OIDC discovery - returns test config
      when(() => mockDiscoveryService.discover(any()))
          .thenAnswer((_) async => testSsoConfig);
    });

    test('returns LoginAttemptSuccess on mobile login success', () async {
      when(() => mockAuthProvider.login('server1', any()))
          .thenAnswer((_) async => LoginSuccess(testToken));
      when(() => mockAuthProvider.getCurrentUser('server1', any()))
          .thenAnswer((_) async => testUser);

      final result = await orchestrator.login(testAuthSystem, 'server1');

      expect(result, isA<LoginAttemptSuccess>());
      final success = result as LoginAttemptSuccess;
      expect(success.user, equals(testUser));
      expect(success.config, equals(testSsoConfig));
    });

    test('returns LoginAttemptRedirect on web login redirect', () async {
      when(() => mockAuthProvider.login('server1', any()))
          .thenAnswer((_) async => const LoginRedirect(serverId: 'server1'));

      final result = await orchestrator.login(testAuthSystem, 'server1');

      expect(result, isA<LoginAttemptRedirect>());
    });

    test('returns LoginAttemptFailure on AuthError', () async {
      when(() => mockAuthProvider.login('server1', any())).thenThrow(
        const AuthErrorNetwork(message: 'Network unavailable'),
      );

      final result = await orchestrator.login(testAuthSystem, 'server1');

      expect(result, isA<LoginAttemptFailure>());
      final failure = result as LoginAttemptFailure;
      expect(failure.message, contains('Network unavailable'));
    });

    test('returns LoginAttemptFailure on OIDC discovery AuthError', () async {
      when(() => mockDiscoveryService.discover(any())).thenThrow(
        const AuthErrorNetwork(message: 'Connection refused'),
      );

      final result = await orchestrator.login(testAuthSystem, 'server1');

      expect(result, isA<LoginAttemptFailure>());
      final failure = result as LoginAttemptFailure;
      expect(failure.message, startsWith('OIDC discovery failed:'));
      expect(failure.message, contains('Connection refused'));
    });

    test('returns LoginAttemptFailure on OIDC discovery Exception', () async {
      when(() => mockDiscoveryService.discover(any()))
          .thenThrow(Exception('Network error'));

      final result = await orchestrator.login(testAuthSystem, 'server1');

      expect(result, isA<LoginAttemptFailure>());
      final failure = result as LoginAttemptFailure;
      expect(failure.message, startsWith('OIDC discovery failed:'));
    });

    test('returns LoginAttemptFailure on generic Exception', () async {
      when(() => mockAuthProvider.login('server1', any()))
          .thenThrow(Exception('Something went wrong'));

      final result = await orchestrator.login(testAuthSystem, 'server1');

      expect(result, isA<LoginAttemptFailure>());
      final failure = result as LoginAttemptFailure;
      expect(failure.message, contains('Something went wrong'));
    });
  });
}
