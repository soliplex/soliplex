import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('TokenResult', () {
    group('TokenFound', () {
      test('creates with token', () {
        final token = AuthToken(
          accessToken: 'access-123',
          expiresAt: DateTime.utc(2025),
        );
        final result = TokenFound(token);

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
        final result1 = TokenFound(token1);
        final result2 = TokenFound(token2);

        expect(result1, equals(result2));
      });

      test('not equal when tokens differ', () {
        final result1 = TokenFound(
          AuthToken(
            accessToken: 'access-123',
            expiresAt: DateTime.utc(2025),
          ),
        );
        final result2 = TokenFound(
          AuthToken(
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
        final result1 = TokenFound(token1);
        final result2 = TokenFound(token2);

        expect(result1.hashCode, equals(result2.hashCode));
      });

      test('toString includes token', () {
        final result = TokenFound(
          AuthToken(
            accessToken: 'access-123',
            expiresAt: DateTime.utc(2025),
          ),
        );

        expect(result.toString(), contains('TokenFound'));
      });
    });

    group('TokenNotFound', () {
      test('creates successfully', () {
        const result = TokenNotFound();

        expect(result, isA<TokenResult>());
      });

      test('equal to another TokenNotFound', () {
        const result1 = TokenNotFound();
        const result2 = TokenNotFound();

        expect(result1, equals(result2));
      });

      test('hashCode consistent with equality', () {
        const result1 = TokenNotFound();
        const result2 = TokenNotFound();

        expect(result1.hashCode, equals(result2.hashCode));
      });

      test('toString includes type', () {
        const result = TokenNotFound();

        expect(result.toString(), equals('TokenNotFound()'));
      });
    });

    group('cross-type equality', () {
      test('TokenFound is not equal to TokenNotFound', () {
        final tokenFound = TokenFound(
          AuthToken(
            accessToken: 'access-123',
            expiresAt: DateTime.utc(2025),
          ),
        );
        const tokenNotFound = TokenNotFound();

        expect(tokenFound, isNot(equals(tokenNotFound)));
      });
    });

    group('sealed class exhaustiveness', () {
      test('can pattern match on all variants', () {
        final results = <TokenResult>[
          TokenFound(
            AuthToken(
              accessToken: 'test',
              expiresAt: DateTime.utc(2025),
            ),
          ),
          const TokenNotFound(),
        ];

        for (final result in results) {
          // Exhaustive switch should compile without 'default' case
          final description = switch (result) {
            TokenFound(:final token) => 'found: ${token.accessToken}',
            TokenNotFound() => 'not found',
          };
          expect(description, isNotEmpty);
        }
      });
    });
  });
}
