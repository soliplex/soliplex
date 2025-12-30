import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

class MockTokenStorage extends Mock implements TokenStorage {}

class FakeAuthToken extends Fake implements AuthToken {}

void main() {
  late MockTokenStorage mockStorage;
  late TokenValidator validator;

  setUpAll(() {
    registerFallbackValue(FakeAuthToken());
  });

  setUp(() {
    mockStorage = MockTokenStorage();
    validator = TokenValidator(tokenStorage: mockStorage);
  });

  AuthToken createToken({
    String accessToken = 'access-123',
    String? refreshToken = 'refresh-456',
    DateTime? expiresAt,
  }) {
    return AuthToken(
      accessToken: accessToken,
      refreshToken: refreshToken,
      expiresAt:
          expiresAt ?? DateTime.now().toUtc().add(const Duration(hours: 1)),
    );
  }

  group('TokenValidator', () {
    group('getValidToken', () {
      test('returns NoToken when no token stored', () async {
        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => const TokenNotFound());

        final result = await validator.getValidToken(
          'server1',
          onRefresh: (_) async => const RefreshRejected('should not be called'),
        );

        expect(result, isA<NoToken>());
      });

      test('returns StorageUnavailable on TokenStorageError', () async {
        when(() => mockStorage.read('server1')).thenAnswer(
          (_) async => const TokenStorageError(message: 'Storage locked'),
        );

        final result = await validator.getValidToken(
          'server1',
          onRefresh: (_) async => const RefreshRejected('should not be called'),
        );

        expect(result, isA<StorageUnavailable>());
        expect(
            (result as StorageUnavailable).message, equals('Storage locked'));
      });

      test('returns Authenticated when token is valid', () async {
        final token = createToken();
        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(token));

        final result = await validator.getValidToken(
          'server1',
          onRefresh: (_) async => const RefreshRejected('should not be called'),
        );

        expect(result, isA<Authenticated>());
        expect((result as Authenticated).token, equals(token));
      });

      test('returns TokenExpired when token expired without refresh', () async {
        final expiredToken = createToken(
          expiresAt: DateTime.now().toUtc().subtract(const Duration(hours: 1)),
          refreshToken: null,
        );
        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(expiredToken));
        when(() => mockStorage.delete('server1')).thenAnswer((_) async {});

        final result = await validator.getValidToken(
          'server1',
          onRefresh: (_) async => const RefreshRejected('should not be called'),
        );

        expect(result, isA<TokenExpired>());
        verify(() => mockStorage.delete('server1')).called(1);
      });

      test('refreshes token and returns Authenticated on success', () async {
        final expiredToken = createToken(
          expiresAt: DateTime.now().toUtc().subtract(const Duration(hours: 1)),
        );
        final newToken = createToken(accessToken: 'new-access');

        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(expiredToken));
        when(() => mockStorage.write('server1', any()))
            .thenAnswer((_) async {});

        final result = await validator.getValidToken(
          'server1',
          onRefresh: (_) async => RefreshSuccess(newToken),
        );

        expect(result, isA<Authenticated>());
        final auth = result as Authenticated;
        expect(auth.token.accessToken, equals('new-access'));
        verify(() => mockStorage.write('server1', newToken)).called(1);
      });

      test('returns RefreshFailed when refresh is rejected', () async {
        final expiredToken = createToken(
          expiresAt: DateTime.now().toUtc().subtract(const Duration(hours: 1)),
        );

        when(() => mockStorage.read('server1'))
            .thenAnswer((_) async => TokenFound(expiredToken));
        when(() => mockStorage.delete('server1')).thenAnswer((_) async {});

        final result = await validator.getValidToken(
          'server1',
          onRefresh: (_) async => const RefreshRejected('invalid_grant'),
        );

        expect(result, isA<RefreshFailed>());
        expect((result as RefreshFailed).cause, equals('invalid_grant'));
        verify(() => mockStorage.delete('server1')).called(1);
      });
    });
  });
}
