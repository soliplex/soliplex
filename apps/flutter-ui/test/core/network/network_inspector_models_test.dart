import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/core/network/network_inspector_models.dart';

void main() {
  group('NetworkEntry', () {
    group('factory NetworkEntry.request', () {
      test('creates entry with request data', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {'Content-Type': 'application/json'},
          body: {'key': 'value'},
        );

        expect(entry.id, equals('test-id'));
        expect(entry.method, equals('POST'));
        expect(entry.uri.toString(), equals('https://example.com/api/test'));
        expect(
          entry.requestHeaders,
          equals({'Content-Type': 'application/json'}),
        );
        expect(entry.requestBody, equals({'key': 'value'}));
        expect(entry.startTime, isNotNull);
        expect(entry.statusCode, isNull);
        expect(entry.responseHeaders, isNull);
        expect(entry.responseBody, isNull);
        expect(entry.endTime, isNull);
        expect(entry.error, isNull);
      });

      test('creates entry with null body', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        );

        expect(entry.requestBody, isNull);
      });

      test('makes headers unmodifiable', () {
        final headers = {'Content-Type': 'application/json'};
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: headers,
        );

        expect(
          () => entry.requestHeaders['New-Header'] = 'value',
          throwsA(isA<UnsupportedError>()),
        );
      });
    });

    group('withResponse', () {
      test('creates copy with response data', () {
        final request = NetworkEntry.request(
          id: 'test-id',
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {'Content-Type': 'application/json'},
          body: {'key': 'value'},
        );

        final response = request.withResponse(
          statusCode: 200,
          headers: {'Content-Type': 'application/json'},
          body: {'result': 'success'},
        );

        // Original request data preserved
        expect(response.id, equals('test-id'));
        expect(response.method, equals('POST'));
        expect(response.uri.toString(), equals('https://example.com/api/test'));
        expect(
          response.requestHeaders,
          equals({'Content-Type': 'application/json'}),
        );
        expect(response.requestBody, equals({'key': 'value'}));
        expect(response.startTime, equals(request.startTime));

        // Response data added
        expect(response.statusCode, equals(200));
        expect(
          response.responseHeaders,
          equals({'Content-Type': 'application/json'}),
        );
        expect(response.responseBody, equals({'result': 'success'}));
        expect(response.endTime, isNotNull);
        expect(response.error, isNull);
      });

      test('makes response headers unmodifiable', () {
        final request = NetworkEntry.request(
          id: 'test-id',
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        );

        final response = request.withResponse(
          statusCode: 200,
          headers: {'Content-Type': 'text/plain'},
          body: 'OK',
        );

        expect(
          () => response.responseHeaders!['New-Header'] = 'value',
          throwsA(isA<UnsupportedError>()),
        );
      });
    });

    group('withError', () {
      test('creates copy with error data', () {
        final request = NetworkEntry.request(
          id: 'test-id',
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        );

        final errorEntry = request.withError('Connection refused');

        // Original request data preserved
        expect(errorEntry.id, equals('test-id'));
        expect(errorEntry.method, equals('POST'));
        expect(errorEntry.startTime, equals(request.startTime));

        // Error data added
        expect(errorEntry.error, equals('Connection refused'));
        expect(errorEntry.endTime, isNotNull);
        expect(errorEntry.statusCode, isNull);
        expect(errorEntry.responseHeaders, isNull);
        expect(errorEntry.responseBody, isNull);
      });
    });

    group('computed properties', () {
      group('latency', () {
        test('returns null when endTime is null', () {
          final entry = NetworkEntry.request(
            id: 'test-id',
            method: 'GET',
            uri: Uri.parse('https://example.com/api/test'),
            headers: {},
          );

          expect(entry.latency, isNull);
          expect(entry.latencyMs, isNull);
        });

        test('returns duration when endTime is set', () {
          final entry = NetworkEntry.request(
            id: 'test-id',
            method: 'GET',
            uri: Uri.parse('https://example.com/api/test'),
            headers: {},
          ).withResponse(statusCode: 200, headers: {});

          expect(entry.latency, isNotNull);
          expect(entry.latencyMs, isNotNull);
          expect(entry.latencyMs, greaterThanOrEqualTo(0));
        });
      });

      group('isComplete', () {
        test('returns false when in-flight', () {
          final entry = NetworkEntry.request(
            id: 'test-id',
            method: 'GET',
            uri: Uri.parse('https://example.com/api/test'),
            headers: {},
          );

          expect(entry.isComplete, isFalse);
        });

        test('returns true when has statusCode', () {
          final entry = NetworkEntry.request(
            id: 'test-id',
            method: 'GET',
            uri: Uri.parse('https://example.com/api/test'),
            headers: {},
          ).withResponse(statusCode: 200, headers: {});

          expect(entry.isComplete, isTrue);
        });

        test('returns true when has error', () {
          final entry = NetworkEntry.request(
            id: 'test-id',
            method: 'GET',
            uri: Uri.parse('https://example.com/api/test'),
            headers: {},
          ).withError('Network error');

          expect(entry.isComplete, isTrue);
        });
      });

      group('isInFlight', () {
        test('returns true when not complete', () {
          final entry = NetworkEntry.request(
            id: 'test-id',
            method: 'GET',
            uri: Uri.parse('https://example.com/api/test'),
            headers: {},
          );

          expect(entry.isInFlight, isTrue);
        });

        test('returns false when complete', () {
          final entry = NetworkEntry.request(
            id: 'test-id',
            method: 'GET',
            uri: Uri.parse('https://example.com/api/test'),
            headers: {},
          ).withResponse(statusCode: 200, headers: {});

          expect(entry.isInFlight, isFalse);
        });
      });

      group('isSuccess', () {
        test('returns false when in-flight', () {
          final entry = NetworkEntry.request(
            id: 'test-id',
            method: 'GET',
            uri: Uri.parse('https://example.com/api/test'),
            headers: {},
          );

          expect(entry.isSuccess, isFalse);
        });

        test('returns true for 2xx status codes', () {
          for (final statusCode in [200, 201, 204, 299]) {
            final entry = NetworkEntry.request(
              id: 'test-id',
              method: 'GET',
              uri: Uri.parse('https://example.com/api/test'),
              headers: {},
            ).withResponse(statusCode: statusCode, headers: {});

            expect(
              entry.isSuccess,
              isTrue,
              reason: 'Status $statusCode should be success',
            );
          }
        });

        test('returns false for non-2xx status codes', () {
          for (final statusCode in [100, 301, 400, 404, 500, 503]) {
            final entry = NetworkEntry.request(
              id: 'test-id',
              method: 'GET',
              uri: Uri.parse('https://example.com/api/test'),
              headers: {},
            ).withResponse(statusCode: statusCode, headers: {});

            expect(
              entry.isSuccess,
              isFalse,
              reason: 'Status $statusCode should not be success',
            );
          }
        });
      });

      group('isError', () {
        test('returns false when in-flight', () {
          final entry = NetworkEntry.request(
            id: 'test-id',
            method: 'GET',
            uri: Uri.parse('https://example.com/api/test'),
            headers: {},
          );

          expect(entry.isError, isFalse);
        });

        test('returns true when has error message', () {
          final entry = NetworkEntry.request(
            id: 'test-id',
            method: 'GET',
            uri: Uri.parse('https://example.com/api/test'),
            headers: {},
          ).withError('Network error');

          expect(entry.isError, isTrue);
        });

        test('returns true for 4xx status codes', () {
          for (final statusCode in [400, 401, 403, 404, 422]) {
            final entry = NetworkEntry.request(
              id: 'test-id',
              method: 'GET',
              uri: Uri.parse('https://example.com/api/test'),
              headers: {},
            ).withResponse(statusCode: statusCode, headers: {});

            expect(
              entry.isError,
              isTrue,
              reason: 'Status $statusCode should be error',
            );
          }
        });

        test('returns true for 5xx status codes', () {
          for (final statusCode in [500, 502, 503, 504]) {
            final entry = NetworkEntry.request(
              id: 'test-id',
              method: 'GET',
              uri: Uri.parse('https://example.com/api/test'),
              headers: {},
            ).withResponse(statusCode: statusCode, headers: {});

            expect(
              entry.isError,
              isTrue,
              reason: 'Status $statusCode should be error',
            );
          }
        });

        test('returns false for 2xx status codes', () {
          final entry = NetworkEntry.request(
            id: 'test-id',
            method: 'GET',
            uri: Uri.parse('https://example.com/api/test'),
            headers: {},
          ).withResponse(statusCode: 200, headers: {});

          expect(entry.isError, isFalse);
        });
      });

      group('shortPath', () {
        test('returns path unchanged when short', () {
          final entry = NetworkEntry.request(
            id: 'test-id',
            method: 'GET',
            uri: Uri.parse('https://example.com/api/test'),
            headers: {},
          );

          expect(entry.shortPath, equals('/api/test'));
        });

        test('truncates long paths', () {
          final longPath = '/api/${'a' * 100}';
          final entry = NetworkEntry.request(
            id: 'test-id',
            method: 'GET',
            uri: Uri.parse('https://example.com$longPath'),
            headers: {},
          );

          expect(entry.shortPath.length, equals(50));
          expect(entry.shortPath, endsWith('...'));
        });
      });

      group('fullUrl', () {
        test('returns complete URL', () {
          final entry = NetworkEntry.request(
            id: 'test-id',
            method: 'GET',
            uri: Uri.parse('https://example.com/api/test?foo=bar'),
            headers: {},
          );

          expect(entry.fullUrl, equals('https://example.com/api/test?foo=bar'));
        });
      });
    });

    group('content type detection', () {
      test('requestContentType handles case variations', () {
        final lowerCase = NetworkEntry.request(
          id: 'test-id',
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {'content-type': 'application/json'},
        );
        expect(lowerCase.requestContentType, equals('application/json'));

        final upperCase = NetworkEntry.request(
          id: 'test-id',
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {'Content-Type': 'application/json'},
        );
        expect(upperCase.requestContentType, equals('application/json'));
      });

      test('isJsonRequest detects JSON content type', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {'Content-Type': 'application/json'},
        );

        expect(entry.isJsonRequest, isTrue);
      });

      test('isJsonRequest detects Map body', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
          body: {'key': 'value'},
        );

        expect(entry.isJsonRequest, isTrue);
      });

      test('isJsonRequest detects List body', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
          body: [1, 2, 3],
        );

        expect(entry.isJsonRequest, isTrue);
      });

      test('isBinaryResponse detects binary content types', () {
        final binaryTypes = [
          'image/png',
          'image/jpeg',
          'audio/mp3',
          'video/mp4',
          'application/octet-stream',
          'application/pdf',
        ];

        for (final contentType in binaryTypes) {
          final entry =
              NetworkEntry.request(
                id: 'test-id',
                method: 'GET',
                uri: Uri.parse('https://example.com/api/test'),
                headers: {},
              ).withResponse(
                statusCode: 200,
                headers: {'Content-Type': contentType},
                body: 'binary data',
              );

          expect(
            entry.isBinaryResponse,
            isTrue,
            reason: '$contentType should be binary',
          );
        }
      });

      test('isHtmlResponse detects HTML content type', () {
        final entry =
            NetworkEntry.request(
              id: 'test-id',
              method: 'GET',
              uri: Uri.parse('https://example.com/api/test'),
              headers: {},
            ).withResponse(
              statusCode: 200,
              headers: {'Content-Type': 'text/html; charset=utf-8'},
              body: '<html></html>',
            );

        expect(entry.isHtmlResponse, isTrue);
      });
    });

    group('formatRequestBody', () {
      test('returns empty string for null body', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        );

        expect(entry.formatRequestBody(), equals(''));
      });

      test('returns string body unchanged', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
          body: 'plain text body',
        );

        expect(entry.formatRequestBody(), equals('plain text body'));
      });

      test('pretty-prints Map body', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
          body: {'key': 'value'},
        );

        expect(entry.formatRequestBody(), contains('"key": "value"'));
      });

      test('pretty-prints List body', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
          body: [1, 2, 3],
        );

        final formatted = entry.formatRequestBody();
        expect(formatted, contains('1'));
        expect(formatted, contains('2'));
        expect(formatted, contains('3'));
      });
    });

    group('formatResponseBody', () {
      test('returns empty string for null body', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        ).withResponse(statusCode: 204, headers: {});

        expect(entry.formatResponseBody(), equals(''));
      });

      test('returns placeholder for binary content', () {
        final entry =
            NetworkEntry.request(
              id: 'test-id',
              method: 'GET',
              uri: Uri.parse('https://example.com/api/test'),
              headers: {},
            ).withResponse(
              statusCode: 200,
              headers: {'Content-Type': 'image/png'},
              body: 'binary data',
            );

        expect(entry.formatResponseBody(), contains('[Binary data:'));
        expect(entry.formatResponseBody(), contains('image/png'));
      });

      test('pretty-prints JSON string response', () {
        final entry =
            NetworkEntry.request(
              id: 'test-id',
              method: 'GET',
              uri: Uri.parse('https://example.com/api/test'),
              headers: {},
            ).withResponse(
              statusCode: 200,
              headers: {'Content-Type': 'application/json'},
              body: '{"key":"value"}',
            );

        expect(entry.formatResponseBody(), contains('"key": "value"'));
      });

      test('returns string as-is when not JSON', () {
        final entry =
            NetworkEntry.request(
              id: 'test-id',
              method: 'GET',
              uri: Uri.parse('https://example.com/api/test'),
              headers: {},
            ).withResponse(
              statusCode: 200,
              headers: {'Content-Type': 'text/plain'},
              body: 'plain text response',
            );

        expect(entry.formatResponseBody(), equals('plain text response'));
      });
    });

    group('toCurl', () {
      test('generates basic GET curl command', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        );

        final curl = entry.toCurl();
        expect(curl, contains('curl'));
        expect(curl, contains("'https://example.com/api/test'"));
        expect(curl, isNot(contains('-X'))); // GET doesn't need -X
      });

      test('includes -X for non-GET methods', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        );

        final curl = entry.toCurl();
        expect(curl, contains("-X 'POST'"));
      });

      test('includes headers', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {
            'Authorization': 'Bearer token',
            'Accept': 'application/json',
          },
        );

        final curl = entry.toCurl();
        expect(curl, contains("-H 'Authorization: Bearer token'"));
        expect(curl, contains("-H 'Accept: application/json'"));
      });

      test('skips content-length header', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {'Content-Length': '42'},
        );

        final curl = entry.toCurl();
        expect(curl, isNot(contains('Content-Length')));
      });

      test('includes body for POST', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {'Content-Type': 'application/json'},
          body: {'key': 'value'},
        );

        final curl = entry.toCurl();
        expect(curl, contains('-d'));
        expect(curl, contains('key'));
        expect(curl, contains('value'));
      });

      test('escapes single quotes in body', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
          body: "it's a test",
        );

        final curl = entry.toCurl();
        expect(curl, contains(r"'\''"));
      });
    });

    group('toString', () {
      test('formats in-flight request', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        );

        expect(entry.toString(), contains('GET'));
        expect(entry.toString(), contains('/api/test'));
        expect(entry.toString(), contains('...'));
      });

      test('formats completed request', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        ).withResponse(statusCode: 200, headers: {});

        expect(entry.toString(), contains('GET'));
        expect(entry.toString(), contains('/api/test'));
        expect(entry.toString(), contains('200'));
        expect(entry.toString(), contains('ms'));
      });

      test('formats error request', () {
        final entry = NetworkEntry.request(
          id: 'test-id',
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        ).withError('Connection refused');

        expect(entry.toString(), contains('GET'));
        expect(entry.toString(), contains('/api/test'));
        expect(entry.toString(), contains('ERR'));
      });
    });
  });
}
