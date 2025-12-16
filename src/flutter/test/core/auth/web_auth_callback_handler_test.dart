import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex/core/auth/callback_params.dart';
import 'package:soliplex/core/auth/oidc_auth_token_response.dart';
import 'package:soliplex/core/auth/secure_token_storage.dart';
import 'package:soliplex/core/auth/web_auth_callback_handler.dart';
import 'package:soliplex/core/auth/web_auth_pending_storage.dart';
import 'package:soliplex/core/services/secure_storage_service.dart';

class MockWebAuthPendingStorage extends Mock implements WebAuthPendingStorage {}

class MockSecureTokenStorage extends Mock implements SecureTokenStorage {}

class MockSecureStorageService extends Mock implements SecureStorageService {}

void main() {
  late MockWebAuthPendingStorage mockPendingStorage;
  late MockSecureTokenStorage mockTokenStorage;
  late MockSecureStorageService mockSecureStorageService;
  late WebAuthCallbackHandler handler;

  setUp(() {
    mockPendingStorage = MockWebAuthPendingStorage();
    mockTokenStorage = MockSecureTokenStorage();
    mockSecureStorageService = MockSecureStorageService();
    handler = WebAuthCallbackHandler(
      pendingStorage: mockPendingStorage,
      tokenStorage: mockTokenStorage,
      secureStorageService: mockSecureStorageService,
    );
  });

  setUpAll(() {
    registerFallbackValue(
      OidcAuthTokenResponse(
        idToken: '',
        accessToken: '',
        accessTokenExpiration: DateTime.now(),
        refreshToken: '',
      ),
    );
  });

  group('WebAuthCallbackHandler', () {
    group('isAuthCallback', () {
      test('returns false on non-web platforms', () {
        // On non-web platforms, the stub implementation always returns false
        expect(handler.isAuthCallback(), isFalse);
      });
    });

    group('getCurrentPath', () {
      test('returns empty string on non-web platforms', () {
        // On non-web platforms, the stub implementation returns ''
        expect(handler.getCurrentPath(), isEmpty);
      });
    });

    group('handleCallback', () {
      test(
        'returns AuthCallbackNotDetected when not on callback URL',
        () async {
          // On non-web platforms, isAuthCallback() returns false
          final result = await handler.handleCallback();

          expect(result, isA<AuthCallbackNotDetected>());
        },
      );
    });
  });

  group('CallbackParams', () {
    group('BackendMediatedCallbackParams', () {
      test('hasError returns true when error is present', () {
        const params = BackendMediatedCallbackParams(
          error: 'access_denied',
        );

        expect(params.hasError, isTrue);
        expect(params.error, equals('access_denied'));
      });

      test('hasError returns false when no error', () {
        const params = BackendMediatedCallbackParams(
          accessToken: 'token123',
          refreshToken: 'refresh123',
          expiresIn: 3600,
        );

        expect(params.hasError, isFalse);
        expect(params.accessToken, equals('token123'));
        expect(params.refreshToken, equals('refresh123'));
        expect(params.expiresIn, equals(3600));
      });

      test('toString masks sensitive data', () {
        const params = BackendMediatedCallbackParams(
          accessToken: 'token123',
          refreshToken: 'refresh123',
          expiresIn: 3600,
        );

        final str = params.toString();
        expect(str, contains('hasAccessToken: true'));
        expect(str, contains('hasRefreshToken: true'));
        expect(str, contains('expiresIn: 3600'));
        // Should not contain actual token values
        expect(str.contains('token123'), isFalse);
      });
    });

    group('PkceCallbackParams', () {
      test('hasError returns true when error is present', () {
        const params = PkceCallbackParams(
          error: 'invalid_grant',
        );

        expect(params.hasError, isTrue);
        expect(params.error, equals('invalid_grant'));
      });

      test('hasError returns false when no error', () {
        const params = PkceCallbackParams(
          code: 'authcode123',
          state: 'state456',
        );

        expect(params.hasError, isFalse);
        expect(params.code, equals('authcode123'));
        expect(params.state, equals('state456'));
      });

      test('toString masks sensitive data', () {
        const params = PkceCallbackParams(
          code: 'authcode123',
          state: 'state456',
        );

        final str = params.toString();
        expect(str, contains('hasCode: true'));
        expect(str, contains('hasState: true'));
        // Should not contain actual code values
        expect(str.contains('authcode123'), isFalse);
      });
    });

    group('NoCallbackParams', () {
      test('has no error', () {
        const params = NoCallbackParams();

        expect(params.hasError, isFalse);
        expect(params.error, isNull);
      });

      test('toString returns expected string', () {
        const params = NoCallbackParams();

        expect(params.toString(), equals('NoCallbackParams()'));
      });
    });
  });

  group('AuthCallbackResult', () {
    group('AuthCallbackSuccess', () {
      test('contains serverId and tokens', () {
        final tokens = OidcAuthTokenResponse(
          idToken: 'id123',
          accessToken: 'access123',
          accessTokenExpiration: DateTime.now(),
          refreshToken: 'refresh123',
        );

        final result = AuthCallbackSuccess(
          serverId: 'server-1',
          tokens: tokens,
        );

        expect(result.serverId, equals('server-1'));
        expect(result.tokens.accessToken, equals('access123'));
      });
    });

    group('AuthCallbackFailure', () {
      test('contains error message', () {
        final result = AuthCallbackFailure(
          error: 'Token exchange failed',
        );

        expect(result.error, equals('Token exchange failed'));
        expect(result.description, isNull);
        expect(result.toString(), equals('Token exchange failed'));
      });

      test('contains error with description', () {
        final result = AuthCallbackFailure(
          error: 'Token exchange failed',
          description: 'The server returned an invalid response',
        );

        expect(result.error, equals('Token exchange failed'));
        expect(
          result.description,
          equals('The server returned an invalid response'),
        );
        expect(
          result.toString(),
          equals(
            'Token exchange failed: The server returned an invalid response',
          ),
        );
      });
    });
  });

  group('OidcWebRedirectException', () {
    test('contains serverId', () {
      final exception = OidcWebRedirectException('server-123');

      expect(exception.serverId, equals('server-123'));
    });

    test('toString includes serverId', () {
      final exception = OidcWebRedirectException('server-123');

      expect(
        exception.toString(),
        contains('server-123'),
      );
    });
  });
}
