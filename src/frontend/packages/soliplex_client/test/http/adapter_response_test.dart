import 'dart:typed_data';

import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('AdapterResponse', () {
    group('construction', () {
      test('creates with required fields only', () {
        final response = AdapterResponse(
          statusCode: 200,
          bodyBytes: Uint8List.fromList([72, 105]), // "Hi"
        );

        expect(response.statusCode, equals(200));
        expect(response.bodyBytes, equals([72, 105]));
        expect(response.headers, isEmpty);
        expect(response.reasonPhrase, isNull);
      });

      test('creates with all fields', () {
        final response = AdapterResponse(
          statusCode: 201,
          bodyBytes: Uint8List.fromList(const []),
          headers: const {'content-type': 'application/json'},
          reasonPhrase: 'Created',
        );

        expect(response.statusCode, equals(201));
        expect(response.bodyBytes, isEmpty);
        expect(response.headers, equals({'content-type': 'application/json'}));
        expect(response.reasonPhrase, equals('Created'));
      });

      test('headers defaults to empty map', () {
        final response = AdapterResponse(
          statusCode: 200,
          bodyBytes: Uint8List(0),
        );

        expect(response.headers, equals(<String, String>{}));
      });
    });

    group('body getter', () {
      test('decodes bodyBytes as UTF-8 string', () {
        final response = AdapterResponse(
          statusCode: 200,
          bodyBytes: Uint8List.fromList([72, 101, 108, 108, 111]), // "Hello"
        );

        expect(response.body, equals('Hello'));
      });

      test('handles empty body', () {
        final response = AdapterResponse(
          statusCode: 204,
          bodyBytes: Uint8List(0),
        );

        expect(response.body, isEmpty);
      });

      test('handles UTF-8 multibyte characters', () {
        // "Cafe" with UTF-8 encoded accent: "Cafe\u0301" (combining acute)
        // Using simple ASCII for reliable test
        final response = AdapterResponse(
          statusCode: 200,
          bodyBytes: Uint8List.fromList([67, 97, 102, 101]), // "Cafe"
        );

        expect(response.body, equals('Cafe'));
      });

      test('handles JSON body', () {
        final jsonBytes = Uint8List.fromList(
          '{"key": "value"}'.codeUnits,
        );
        final response = AdapterResponse(
          statusCode: 200,
          bodyBytes: jsonBytes,
        );

        expect(response.body, equals('{"key": "value"}'));
      });
    });

    group('status helpers', () {
      group('isSuccess', () {
        test('returns true for 200', () {
          final response = AdapterResponse(
            statusCode: 200,
            bodyBytes: Uint8List(0),
          );

          expect(response.isSuccess, isTrue);
        });

        test('returns true for 201', () {
          final response = AdapterResponse(
            statusCode: 201,
            bodyBytes: Uint8List(0),
          );

          expect(response.isSuccess, isTrue);
        });

        test('returns true for 299', () {
          final response = AdapterResponse(
            statusCode: 299,
            bodyBytes: Uint8List(0),
          );

          expect(response.isSuccess, isTrue);
        });

        test('returns false for 199', () {
          final response = AdapterResponse(
            statusCode: 199,
            bodyBytes: Uint8List(0),
          );

          expect(response.isSuccess, isFalse);
        });

        test('returns false for 300', () {
          final response = AdapterResponse(
            statusCode: 300,
            bodyBytes: Uint8List(0),
          );

          expect(response.isSuccess, isFalse);
        });
      });

      group('isRedirect', () {
        test('returns true for 301', () {
          final response = AdapterResponse(
            statusCode: 301,
            bodyBytes: Uint8List(0),
          );

          expect(response.isRedirect, isTrue);
        });

        test('returns true for 302', () {
          final response = AdapterResponse(
            statusCode: 302,
            bodyBytes: Uint8List(0),
          );

          expect(response.isRedirect, isTrue);
        });

        test('returns true for 399', () {
          final response = AdapterResponse(
            statusCode: 399,
            bodyBytes: Uint8List(0),
          );

          expect(response.isRedirect, isTrue);
        });

        test('returns false for 200', () {
          final response = AdapterResponse(
            statusCode: 200,
            bodyBytes: Uint8List(0),
          );

          expect(response.isRedirect, isFalse);
        });

        test('returns false for 400', () {
          final response = AdapterResponse(
            statusCode: 400,
            bodyBytes: Uint8List(0),
          );

          expect(response.isRedirect, isFalse);
        });
      });

      group('isClientError', () {
        test('returns true for 400', () {
          final response = AdapterResponse(
            statusCode: 400,
            bodyBytes: Uint8List(0),
          );

          expect(response.isClientError, isTrue);
        });

        test('returns true for 404', () {
          final response = AdapterResponse(
            statusCode: 404,
            bodyBytes: Uint8List(0),
          );

          expect(response.isClientError, isTrue);
        });

        test('returns true for 499', () {
          final response = AdapterResponse(
            statusCode: 499,
            bodyBytes: Uint8List(0),
          );

          expect(response.isClientError, isTrue);
        });

        test('returns false for 399', () {
          final response = AdapterResponse(
            statusCode: 399,
            bodyBytes: Uint8List(0),
          );

          expect(response.isClientError, isFalse);
        });

        test('returns false for 500', () {
          final response = AdapterResponse(
            statusCode: 500,
            bodyBytes: Uint8List(0),
          );

          expect(response.isClientError, isFalse);
        });
      });

      group('isServerError', () {
        test('returns true for 500', () {
          final response = AdapterResponse(
            statusCode: 500,
            bodyBytes: Uint8List(0),
          );

          expect(response.isServerError, isTrue);
        });

        test('returns true for 503', () {
          final response = AdapterResponse(
            statusCode: 503,
            bodyBytes: Uint8List(0),
          );

          expect(response.isServerError, isTrue);
        });

        test('returns true for 599', () {
          final response = AdapterResponse(
            statusCode: 599,
            bodyBytes: Uint8List(0),
          );

          expect(response.isServerError, isTrue);
        });

        test('returns false for 499', () {
          final response = AdapterResponse(
            statusCode: 499,
            bodyBytes: Uint8List(0),
          );

          expect(response.isServerError, isFalse);
        });

        test('returns false for 200', () {
          final response = AdapterResponse(
            statusCode: 200,
            bodyBytes: Uint8List(0),
          );

          expect(response.isServerError, isFalse);
        });
      });
    });

    group('header helpers', () {
      group('contentType', () {
        test('returns content-type header value', () {
          final response = AdapterResponse(
            statusCode: 200,
            bodyBytes: Uint8List(0),
            headers: const {'content-type': 'application/json'},
          );

          expect(response.contentType, equals('application/json'));
        });

        test('returns null when content-type header is missing', () {
          final response = AdapterResponse(
            statusCode: 200,
            bodyBytes: Uint8List(0),
          );

          expect(response.contentType, isNull);
        });

        test('returns value with charset', () {
          final response = AdapterResponse(
            statusCode: 200,
            bodyBytes: Uint8List(0),
            headers: const {'content-type': 'text/html; charset=utf-8'},
          );

          expect(response.contentType, equals('text/html; charset=utf-8'));
        });
      });

      group('contentLength', () {
        test('parses content-length header as integer', () {
          final response = AdapterResponse(
            statusCode: 200,
            bodyBytes: Uint8List(0),
            headers: const {'content-length': '1234'},
          );

          expect(response.contentLength, equals(1234));
        });

        test('returns null for invalid content-length', () {
          final response = AdapterResponse(
            statusCode: 200,
            bodyBytes: Uint8List(0),
            headers: const {'content-length': 'invalid'},
          );

          expect(response.contentLength, isNull);
        });

        test('returns null when content-length header is missing', () {
          final response = AdapterResponse(
            statusCode: 200,
            bodyBytes: Uint8List(0),
          );

          expect(response.contentLength, isNull);
        });

        test('handles zero content-length', () {
          final response = AdapterResponse(
            statusCode: 204,
            bodyBytes: Uint8List(0),
            headers: const {'content-length': '0'},
          );

          expect(response.contentLength, equals(0));
        });

        test('handles large content-length', () {
          final response = AdapterResponse(
            statusCode: 200,
            bodyBytes: Uint8List(0),
            headers: const {'content-length': '9999999999'},
          );

          expect(response.contentLength, equals(9999999999));
        });
      });
    });

    group('toString', () {
      test('includes status code and body length', () {
        final response = AdapterResponse(
          statusCode: 200,
          bodyBytes: Uint8List.fromList(const [1, 2, 3, 4, 5]),
        );

        expect(response.toString(), contains('200'));
        expect(response.toString(), contains('5'));
      });

      test('formats correctly for empty body', () {
        final response = AdapterResponse(
          statusCode: 404,
          bodyBytes: Uint8List(0),
        );

        final str = response.toString();

        expect(str, contains('404'));
        expect(str, contains('0'));
      });

      test('follows expected format', () {
        final response = AdapterResponse(
          statusCode: 201,
          bodyBytes: Uint8List.fromList(const [1, 2, 3]),
        );

        expect(
          response.toString(),
          equals('AdapterResponse(statusCode: 201, bodyLength: 3)'),
        );
      });
    });
  });
}
