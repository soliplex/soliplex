import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('AuthResult', () {
    group('Authenticated', () {
      test('creates with token', () {
        final token = AuthToken(
          accessToken: 'access-123',
          expiresAt: DateTime.utc(2025),
        );
        final result = Authenticated(token: token);

        expect(result.token, equals(token));
      });

      test('equal when tokens are equal', () {
        final token1 = AuthToken(
          accessToken: 'access-123',
          expiresAt: DateTime.utc(2025),
        );
        final token2 = AuthToken(
          accessToken: 'access-123',
          expiresAt: DateTime.utc(2025),
        );
        final result1 = Authenticated(token: token1);
        final result2 = Authenticated(token: token2);

        expect(result1, equals(result2));
      });

      test('not equal when tokens differ', () {
        final result1 = Authenticated(
          token: AuthToken(
            accessToken: 'access-123',
            expiresAt: DateTime.utc(2025),
          ),
        );
        final result2 = Authenticated(
          token: AuthToken(
            accessToken: 'access-456',
            expiresAt: DateTime.utc(2025),
          ),
        );

        expect(result1, isNot(equals(result2)));
      });

      test('hashCode consistent with equality', () {
        final token1 = AuthToken(
          accessToken: 'access-123',
          expiresAt: DateTime.utc(2025),
        );
        final token2 = AuthToken(
          accessToken: 'access-123',
          expiresAt: DateTime.utc(2025),
        );
        final result1 = Authenticated(token: token1);
        final result2 = Authenticated(token: token2);

        expect(result1.hashCode, equals(result2.hashCode));
      });

      test('toString includes type and token', () {
        final result = Authenticated(
          token: AuthToken(
            accessToken: 'access-123',
            expiresAt: DateTime.utc(2025),
          ),
        );

        expect(result.toString(), contains('Authenticated'));
        expect(result.toString(), contains('token'));
      });
    });

    group('NoToken', () {
      test('creates successfully', () {
        const result = NoToken();

        expect(result, isA<NotAuthenticated>());
        expect(result, isA<AuthResult>());
      });

      test('equal to another NoToken', () {
        const result1 = NoToken();
        const result2 = NoToken();

        expect(result1, equals(result2));
      });

      test('hashCode consistent with equality', () {
        const result1 = NoToken();
        const result2 = NoToken();

        expect(result1.hashCode, equals(result2.hashCode));
      });

      test('toString includes type', () {
        const result = NoToken();

        expect(result.toString(), equals('NoToken()'));
      });
    });

    group('TokenExpired', () {
      test('creates successfully', () {
        const result = TokenExpired();

        expect(result, isA<NotAuthenticated>());
        expect(result, isA<AuthResult>());
      });

      test('equal to another TokenExpired', () {
        const result1 = TokenExpired();
        const result2 = TokenExpired();

        expect(result1, equals(result2));
      });

      test('hashCode consistent with equality', () {
        const result1 = TokenExpired();
        const result2 = TokenExpired();

        expect(result1.hashCode, equals(result2.hashCode));
      });

      test('toString includes type', () {
        const result = TokenExpired();

        expect(result.toString(), equals('TokenExpired()'));
      });
    });

    group('RefreshFailed', () {
      test('creates with cause', () {
        final cause = Exception('invalid_grant');
        final result = RefreshFailed(cause: cause);

        expect(result, isA<NotAuthenticated>());
        expect(result.cause, same(cause));
      });

      test('equal when causes are identical', () {
        final cause = Exception('refresh failed');
        final result1 = RefreshFailed(cause: cause);
        final result2 = RefreshFailed(cause: cause);

        expect(result1, equals(result2));
      });

      test('not equal when causes differ', () {
        final result1 = RefreshFailed(cause: Exception('error 1'));
        final result2 = RefreshFailed(cause: Exception('error 2'));

        expect(result1, isNot(equals(result2)));
      });

      test('hashCode consistent with equality', () {
        final cause = Exception('refresh failed');
        final result1 = RefreshFailed(cause: cause);
        final result2 = RefreshFailed(cause: cause);

        expect(result1.hashCode, equals(result2.hashCode));
      });

      test('toString includes cause', () {
        final result = RefreshFailed(cause: Exception('invalid_grant'));

        expect(result.toString(), contains('RefreshFailed'));
        expect(result.toString(), contains('invalid_grant'));
      });
    });

    group('cross-type equality', () {
      test('Authenticated is not equal to NotAuthenticated subtypes', () {
        final authenticated = Authenticated(
          token: AuthToken(
            accessToken: 'access-123',
            expiresAt: DateTime.utc(2025),
          ),
        );

        expect(authenticated, isNot(equals(const NoToken())));
        expect(authenticated, isNot(equals(const TokenExpired())));
        expect(
          authenticated,
          isNot(equals(RefreshFailed(cause: Exception('test')))),
        );
      });

      test('NotAuthenticated subtypes are not equal to each other', () {
        const noToken = NoToken();
        const tokenExpired = TokenExpired();
        final refreshFailed = RefreshFailed(cause: Exception('test'));

        expect(noToken, isNot(equals(tokenExpired)));
        expect(noToken, isNot(equals(refreshFailed)));
        expect(tokenExpired, isNot(equals(refreshFailed)));
      });
    });

    group('sealed class exhaustiveness', () {
      test('can pattern match on all variants', () {
        final results = <AuthResult>[
          Authenticated(
            token: AuthToken(
              accessToken: 'test',
              expiresAt: DateTime.utc(2025),
            ),
          ),
          const NoToken(),
          const TokenExpired(),
          RefreshFailed(cause: Exception('test')),
        ];

        for (final result in results) {
          // Exhaustive switch should compile without 'default' case
          final description = switch (result) {
            Authenticated(:final token) => 'has token: ${token.accessToken}',
            NoToken() => 'no token stored',
            TokenExpired() => 'token expired',
            RefreshFailed(:final cause) => 'refresh failed: $cause',
          };
          expect(description, isNotEmpty);
        }
      });
    });
  });
}
