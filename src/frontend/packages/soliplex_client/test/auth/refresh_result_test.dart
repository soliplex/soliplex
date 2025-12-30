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
