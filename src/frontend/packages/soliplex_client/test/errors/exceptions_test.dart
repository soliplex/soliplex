import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

/// Test-only concrete implementation to test base class behavior.
class _TestException extends SoliplexException {
  const _TestException({required super.message});
}

void main() {
  group('SoliplexException base class', () {
    test('toString returns runtimeType and message', () {
      const exception = _TestException(message: 'Test message');

      expect(exception.toString(), equals('_TestException: Test message'));
    });
  });

  group('AuthException', () {
    test('creates with required message', () {
      const exception = AuthException(message: 'Unauthorized');

      expect(exception.message, equals('Unauthorized'));
      expect(exception.statusCode, isNull);
      expect(exception.originalError, isNull);
      expect(exception.stackTrace, isNull);
    });

    test('creates with all fields', () {
      final originalError = Exception('Original');
      final trace = StackTrace.current;

      final exception = AuthException(
        message: 'Forbidden',
        statusCode: 403,
        originalError: originalError,
        stackTrace: trace,
      );

      expect(exception.message, equals('Forbidden'));
      expect(exception.statusCode, equals(403));
      expect(exception.originalError, equals(originalError));
      expect(exception.stackTrace, equals(trace));
    });

    test('toString with status code', () {
      const exception = AuthException(message: 'Unauthorized', statusCode: 401);

      expect(exception.toString(), equals('AuthException(401): Unauthorized'));
    });

    test('toString without status code', () {
      const exception = AuthException(message: 'Session expired');

      expect(exception.toString(), equals('AuthException: Session expired'));
    });

    test('is SoliplexException', () {
      const exception = AuthException(message: 'Test');

      expect(exception, isA<SoliplexException>());
    });
  });

  group('NetworkException', () {
    test('creates with required message', () {
      const exception = NetworkException(message: 'Connection failed');

      expect(exception.message, equals('Connection failed'));
      expect(exception.isTimeout, isFalse);
      expect(exception.originalError, isNull);
      expect(exception.stackTrace, isNull);
    });

    test('creates with all fields', () {
      final originalError = Exception('Socket error');
      final trace = StackTrace.current;

      final exception = NetworkException(
        message: 'Request timed out',
        isTimeout: true,
        originalError: originalError,
        stackTrace: trace,
      );

      expect(exception.message, equals('Request timed out'));
      expect(exception.isTimeout, isTrue);
      expect(exception.originalError, equals(originalError));
      expect(exception.stackTrace, equals(trace));
    });

    test('toString with timeout', () {
      const exception = NetworkException(
        message: 'Request timed out after 30s',
        isTimeout: true,
      );

      expect(
        exception.toString(),
        equals('NetworkException(timeout): Request timed out after 30s'),
      );
    });

    test('toString without timeout', () {
      const exception = NetworkException(message: 'Host unreachable');

      expect(
        exception.toString(),
        equals('NetworkException: Host unreachable'),
      );
    });

    test('is SoliplexException', () {
      const exception = NetworkException(message: 'Test');

      expect(exception, isA<SoliplexException>());
    });
  });

  group('ApiException', () {
    test('creates with required fields', () {
      const exception = ApiException(
        message: 'Internal server error',
        statusCode: 500,
      );

      expect(exception.message, equals('Internal server error'));
      expect(exception.statusCode, equals(500));
      expect(exception.body, isNull);
      expect(exception.originalError, isNull);
      expect(exception.stackTrace, isNull);
    });

    test('creates with all fields', () {
      final originalError = Exception('HTTP error');
      final trace = StackTrace.current;

      final exception = ApiException(
        message: 'Bad request',
        statusCode: 400,
        body: '{"error": "Invalid input"}',
        originalError: originalError,
        stackTrace: trace,
      );

      expect(exception.message, equals('Bad request'));
      expect(exception.statusCode, equals(400));
      expect(exception.body, equals('{"error": "Invalid input"}'));
      expect(exception.originalError, equals(originalError));
      expect(exception.stackTrace, equals(trace));
    });

    test('toString includes status code', () {
      const exception = ApiException(
        message: 'Service unavailable',
        statusCode: 503,
      );

      expect(
        exception.toString(),
        equals('ApiException(503): Service unavailable'),
      );
    });

    test('is SoliplexException', () {
      const exception = ApiException(message: 'Test', statusCode: 500);

      expect(exception, isA<SoliplexException>());
    });
  });

  group('NotFoundException', () {
    test('creates with required message', () {
      const exception = NotFoundException(message: 'Resource not found');

      expect(exception.message, equals('Resource not found'));
      expect(exception.resource, isNull);
      expect(exception.originalError, isNull);
      expect(exception.stackTrace, isNull);
    });

    test('creates with all fields', () {
      final originalError = Exception('HTTP 404');
      final trace = StackTrace.current;

      final exception = NotFoundException(
        message: 'Room not found',
        resource: 'room-123',
        originalError: originalError,
        stackTrace: trace,
      );

      expect(exception.message, equals('Room not found'));
      expect(exception.resource, equals('room-123'));
      expect(exception.originalError, equals(originalError));
      expect(exception.stackTrace, equals(trace));
    });

    test('toString with resource', () {
      const exception = NotFoundException(
        message: 'Not found',
        resource: 'thread-456',
      );

      expect(
        exception.toString(),
        equals('NotFoundException: thread-456 not found'),
      );
    });

    test('toString without resource', () {
      const exception = NotFoundException(message: 'Page not found');

      expect(
        exception.toString(),
        equals('NotFoundException: Page not found'),
      );
    });

    test('is SoliplexException', () {
      const exception = NotFoundException(message: 'Test');

      expect(exception, isA<SoliplexException>());
    });
  });

  group('CancelledException', () {
    test('creates with no arguments', () {
      const exception = CancelledException();

      expect(exception.message, equals('Operation cancelled'));
      expect(exception.reason, isNull);
      expect(exception.originalError, isNull);
      expect(exception.stackTrace, isNull);
    });

    test('creates with reason', () {
      const exception = CancelledException(reason: 'User requested');

      expect(exception.message, equals('User requested'));
      expect(exception.reason, equals('User requested'));
    });

    test('creates with all fields', () {
      final originalError = Exception('Cancelled');
      final trace = StackTrace.current;

      final exception = CancelledException(
        reason: 'Timeout exceeded',
        originalError: originalError,
        stackTrace: trace,
      );

      expect(exception.reason, equals('Timeout exceeded'));
      expect(exception.originalError, equals(originalError));
      expect(exception.stackTrace, equals(trace));
    });

    test('toString with reason', () {
      const exception = CancelledException(reason: 'User requested');

      expect(
        exception.toString(),
        equals('CancelledException: User requested'),
      );
    });

    test('toString without reason', () {
      const exception = CancelledException();

      expect(exception.toString(), equals('CancelledException'));
    });

    test('is SoliplexException', () {
      const exception = CancelledException();

      expect(exception, isA<SoliplexException>());
    });
  });

  group('SoliplexException hierarchy', () {
    test('all exceptions can be caught as SoliplexException', () {
      final exceptions = <SoliplexException>[
        const AuthException(message: 'Auth error'),
        const NetworkException(message: 'Network error'),
        const ApiException(message: 'API error', statusCode: 500),
        const NotFoundException(message: 'Not found'),
        const CancelledException(),
      ];

      for (final exception in exceptions) {
        expect(exception, isA<SoliplexException>());
        expect(exception, isA<Exception>());
      }
    });

    test('exceptions preserve original error and stack trace', () {
      final originalError = Exception('Root cause');
      final trace = StackTrace.current;

      final exceptions = <SoliplexException>[
        AuthException(
          message: 'Auth',
          originalError: originalError,
          stackTrace: trace,
        ),
        NetworkException(
          message: 'Network',
          originalError: originalError,
          stackTrace: trace,
        ),
        ApiException(
          message: 'API',
          statusCode: 500,
          originalError: originalError,
          stackTrace: trace,
        ),
        NotFoundException(
          message: 'Not found',
          originalError: originalError,
          stackTrace: trace,
        ),
        CancelledException(originalError: originalError, stackTrace: trace),
      ];

      for (final exception in exceptions) {
        expect(exception.originalError, equals(originalError));
        expect(exception.stackTrace, equals(trace));
      }
    });
  });
}
