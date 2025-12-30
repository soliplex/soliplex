import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('RefreshResult', () {
    group('RefreshSuccess', () {
      test('stores token', () {
        final token = AuthToken(
          accessToken: 'access-123',
          refreshToken: 'refresh-456',
          expiresAt: DateTime.now().add(const Duration(hours: 1)),
        );

        final result = RefreshSuccess(token);

        expect(result.token, equals(token));
      });

      test('equality works correctly', () {
        final expiresAt = DateTime.utc(2025, 12, 31);
        final token1 = AuthToken(
          accessToken: 'access-123',
          expiresAt: expiresAt,
        );
        final token2 = AuthToken(
          accessToken: 'access-123',
          expiresAt: expiresAt,
        );

        final result1 = RefreshSuccess(token1);
        final result2 = RefreshSuccess(token2);

        expect(result1, equals(result2));
        expect(result1.hashCode, equals(result2.hashCode));
      });

      test('not equal with different tokens', () {
        final expiresAt = DateTime.utc(2025, 12, 31);
        final result1 = RefreshSuccess(
          AuthToken(accessToken: 'token-1', expiresAt: expiresAt),
        );
        final result2 = RefreshSuccess(
          AuthToken(accessToken: 'token-2', expiresAt: expiresAt),
        );

        expect(result1, isNot(equals(result2)));
      });

      test('toString includes token info', () {
        final token = AuthToken(
          accessToken: 'access-123',
          expiresAt: DateTime.utc(2025, 12, 31),
        );
        final result = RefreshSuccess(token);

        expect(result.toString(), contains('RefreshSuccess'));
      });
    });

    group('RefreshRejected', () {
      test('stores cause', () {
        const result = RefreshRejected('invalid_grant');

        expect(result.cause, equals('invalid_grant'));
      });

      test('can be const', () {
        const result = RefreshRejected('test cause');

        expect(result.cause, equals('test cause'));
      });

      test('equality works correctly', () {
        const result1 = RefreshRejected('invalid_grant');
        const result2 = RefreshRejected('invalid_grant');

        expect(result1, equals(result2));
        expect(result1.hashCode, equals(result2.hashCode));
      });

      test('not equal with different cause', () {
        const result1 = RefreshRejected('invalid_grant');
        const result2 = RefreshRejected('token_expired');

        expect(result1, isNot(equals(result2)));
      });

      test('toString includes cause', () {
        const result = RefreshRejected('invalid_grant');

        expect(result.toString(), contains('RefreshRejected'));
        expect(result.toString(), contains('invalid_grant'));
      });
    });

    group('sealed class exhaustiveness', () {
      test('can pattern match on all variants', () {
        final token = AuthToken(
          accessToken: 'test',
          expiresAt: DateTime.now(),
        );

        final results = <RefreshResult>[
          RefreshSuccess(token),
          const RefreshRejected('error'),
        ];

        for (final result in results) {
          final description = switch (result) {
            RefreshSuccess(:final token) => 'success: ${token.accessToken}',
            RefreshRejected(:final cause) => 'rejected: $cause',
          };
          expect(description, isNotEmpty);
        }
      });
    });
  });
}
