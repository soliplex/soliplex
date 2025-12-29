import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('AuthError', () {
    group('base class', () {
      test('preserves original error and stack trace', () {
        final originalError = FormatException('bad token');
        final trace = StackTrace.current;

        final error = AuthErrorNetwork(
          message: 'refresh failed',
          originalError: originalError,
          stackTrace: trace,
        );

        expect(error.originalError, same(originalError));
        expect(error.stackTrace, same(trace));
      });

      test('original error and stack trace are optional', () {
        const error = AuthErrorNetwork(message: 'failed');

        expect(error.originalError, isNull);
        expect(error.stackTrace, isNull);
      });
    });

    group('AuthErrorCancelled', () {
      test('creates with default message', () {
        const error = AuthErrorCancelled();

        expect(error.message, equals('Authentication cancelled'));
      });

      test('creates with custom message', () {
        const error = AuthErrorCancelled(message: 'User closed login window');

        expect(error.message, equals('User closed login window'));
      });

      test('toString includes type and message', () {
        const error = AuthErrorCancelled();

        expect(error.toString(), contains('Cancelled'));
        expect(error.toString(), contains('Authentication cancelled'));
      });
    });

    group('AuthErrorNetwork', () {
      test('creates with message', () {
        const error = AuthErrorNetwork(message: 'Connection timeout');

        expect(error.message, equals('Connection timeout'));
        expect(error.isTimeout, isFalse);
      });

      test('creates with timeout flag', () {
        const error = AuthErrorNetwork(
          message: 'Request timed out',
          isTimeout: true,
        );

        expect(error.isTimeout, isTrue);
      });

      test('toString includes type and message', () {
        const error = AuthErrorNetwork(message: 'No internet');

        expect(error.toString(), contains('Network'));
        expect(error.toString(), contains('No internet'));
      });
    });

    group('AuthErrorTokenExpired', () {
      test('creates with default message', () {
        const error = AuthErrorTokenExpired();

        expect(error.message, equals('Token has expired'));
      });

      test('creates with custom message', () {
        const error = AuthErrorTokenExpired(message: 'Refresh token expired');

        expect(error.message, equals('Refresh token expired'));
      });

      test('toString includes type and message', () {
        const error = AuthErrorTokenExpired();

        expect(error.toString(), contains('TokenExpired'));
      });
    });

    group('AuthErrorInvalidState', () {
      test('creates with default message', () {
        const error = AuthErrorInvalidState();

        expect(error.message, equals('Invalid CSRF state'));
      });

      test('creates with custom message', () {
        const error = AuthErrorInvalidState(message: 'State mismatch');

        expect(error.message, equals('State mismatch'));
      });

      test('toString includes type and message', () {
        const error = AuthErrorInvalidState();

        expect(error.toString(), contains('InvalidState'));
      });
    });

    group('AuthErrorServer', () {
      test('creates with message and status code', () {
        const error = AuthErrorServer(
          message: 'Internal server error',
          statusCode: 500,
        );

        expect(error.message, equals('Internal server error'));
        expect(error.statusCode, equals(500));
      });

      test('creates with response body', () {
        const error = AuthErrorServer(
          message: 'Bad request',
          statusCode: 400,
          body: '{"error": "invalid_grant"}',
        );

        expect(error.body, equals('{"error": "invalid_grant"}'));
      });

      test('toString includes status code', () {
        const error = AuthErrorServer(
          message: 'Server error',
          statusCode: 500,
        );

        expect(error.toString(), contains('500'));
      });
    });

    group('AuthErrorConfiguration', () {
      test('creates with message', () {
        const error = AuthErrorConfiguration(
          message: 'Missing client ID',
        );

        expect(error.message, equals('Missing client ID'));
      });

      test('toString includes type and message', () {
        const error = AuthErrorConfiguration(
          message: 'Invalid redirect URI',
        );

        expect(error.toString(), contains('Configuration'));
        expect(error.toString(), contains('Invalid redirect URI'));
      });
    });

    group('sealed class exhaustiveness', () {
      test('can pattern match on all variants', () {
        // This test verifies the sealed class is properly exhaustive
        final errors = <AuthError>[
          const AuthErrorCancelled(),
          const AuthErrorNetwork(message: 'test'),
          const AuthErrorTokenExpired(),
          const AuthErrorInvalidState(),
          const AuthErrorServer(message: 'test', statusCode: 500),
          const AuthErrorConfiguration(message: 'test'),
        ];

        for (final error in errors) {
          // Exhaustive switch should compile without 'default' case
          final result = switch (error) {
            AuthErrorCancelled() => 'cancelled',
            AuthErrorNetwork() => 'network',
            AuthErrorTokenExpired() => 'expired',
            AuthErrorInvalidState() => 'invalid_state',
            AuthErrorServer() => 'server',
            AuthErrorConfiguration() => 'config',
          };
          expect(result, isNotEmpty);
        }
      });
    });
  });
}
