import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('UrlBuilder', () {
    group('constructor', () {
      test('accepts valid HTTPS URL', () {
        expect(() => UrlBuilder('https://api.example.com'), returnsNormally);
      });

      test('accepts valid HTTP URL', () {
        expect(() => UrlBuilder('http://localhost:8000'), returnsNormally);
      });

      test('accepts URL with path', () {
        final builder = UrlBuilder('https://api.example.com/v1');
        expect(builder.baseUrl, equals('https://api.example.com/v1'));
      });

      test('throws FormatException for URL without scheme', () {
        expect(
          () => UrlBuilder('api.example.com'),
          throwsA(isA<FormatException>()),
        );
      });

      test('throws FormatException for relative URL', () {
        expect(
          () => UrlBuilder('/api/v1'),
          throwsA(isA<FormatException>()),
        );
      });
    });

    group('baseUrl', () {
      test('returns the base URL', () {
        final builder = UrlBuilder('https://api.example.com');
        expect(builder.baseUrl, equals('https://api.example.com'));
      });

      test('returns URL with port', () {
        final builder = UrlBuilder('http://localhost:8000');
        expect(builder.baseUrl, equals('http://localhost:8000'));
      });
    });

    group('build with path', () {
      test('appends simple path', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build(path: 'rooms');
        expect(uri.toString(), equals('https://api.example.com/rooms'));
      });

      test('appends path with leading slash', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build(path: '/rooms');
        expect(uri.toString(), equals('https://api.example.com/rooms'));
      });

      test('appends path with trailing slash', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build(path: 'rooms/');
        expect(uri.toString(), equals('https://api.example.com/rooms'));
      });

      test('appends nested path', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build(path: 'rooms/123/threads');
        expect(
          uri.toString(),
          equals('https://api.example.com/rooms/123/threads'),
        );
      });

      test('handles empty path', () {
        final builder = UrlBuilder('https://api.example.com/v1');
        final uri = builder.build(path: '');
        expect(uri.toString(), equals('https://api.example.com/v1'));
      });

      test('handles path with multiple slashes', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build(path: '//rooms//threads//');
        expect(
          uri.toString(),
          equals('https://api.example.com/rooms/threads'),
        );
      });
    });

    group('build with pathSegments', () {
      test('appends single segment', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build(pathSegments: ['rooms']);
        expect(uri.toString(), equals('https://api.example.com/rooms'));
      });

      test('appends multiple segments', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build(pathSegments: ['rooms', '123', 'threads']);
        expect(
          uri.toString(),
          equals('https://api.example.com/rooms/123/threads'),
        );
      });

      test('handles empty segments', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build(pathSegments: ['rooms', '', 'threads']);
        expect(
          uri.toString(),
          equals('https://api.example.com/rooms/threads'),
        );
      });

      test('handles segments with slashes', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build(pathSegments: ['rooms/123/threads']);
        expect(
          uri.toString(),
          equals('https://api.example.com/rooms/123/threads'),
        );
      });

      test('handles empty segments list', () {
        final builder = UrlBuilder('https://api.example.com/v1');
        final uri = builder.build(pathSegments: []);
        expect(uri.toString(), equals('https://api.example.com/v1'));
      });
    });

    group('build with path and pathSegments combined', () {
      test('combines path before pathSegments', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build(
          path: 'rooms',
          pathSegments: ['123', 'threads'],
        );
        expect(
          uri.toString(),
          equals('https://api.example.com/rooms/123/threads'),
        );
      });

      test('handles nested path with segments', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build(
          path: 'api/v1',
          pathSegments: ['rooms'],
        );
        expect(
          uri.toString(),
          equals('https://api.example.com/api/v1/rooms'),
        );
      });
    });

    group('build with queryParameters', () {
      test('adds single query parameter', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build(
          path: 'search',
          queryParameters: {'q': 'hello'},
        );
        expect(
          uri.toString(),
          equals('https://api.example.com/search?q=hello'),
        );
      });

      test('adds multiple query parameters', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build(
          path: 'search',
          queryParameters: {'q': 'hello', 'limit': '10'},
        );
        // Order may vary, so check contains
        expect(uri.queryParameters['q'], equals('hello'));
        expect(uri.queryParameters['limit'], equals('10'));
      });

      test('encodes special characters', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build(
          path: 'search',
          queryParameters: {'q': 'hello world'},
        );
        expect(uri.queryParameters['q'], equals('hello world'));
        // Both %20 and + are valid encodings for space in query strings
        expect(
          uri.toString(),
          anyOf(contains('q=hello%20world'), contains('q=hello+world')),
        );
      });

      test('handles empty query parameters', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build(
          path: 'rooms',
          queryParameters: {},
        );
        expect(uri.toString(), equals('https://api.example.com/rooms'));
        expect(uri.hasQuery, isFalse);
      });

      test('handles null query parameters', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build(path: 'rooms');
        expect(uri.hasQuery, isFalse);
      });
    });

    group('build with base URL path', () {
      test('combines base path with new path', () {
        final builder = UrlBuilder('https://api.example.com/v1');
        final uri = builder.build(path: 'rooms');
        expect(uri.toString(), equals('https://api.example.com/v1/rooms'));
      });

      test('combines base path with path segments', () {
        final builder = UrlBuilder('https://api.example.com/api/v1');
        final uri = builder.build(pathSegments: ['rooms', '123']);
        expect(
          uri.toString(),
          equals('https://api.example.com/api/v1/rooms/123'),
        );
      });

      test('handles base URL with trailing slash', () {
        final builder = UrlBuilder('https://api.example.com/v1/');
        final uri = builder.build(path: 'rooms');
        expect(uri.toString(), equals('https://api.example.com/v1/rooms'));
      });
    });

    group('build with no arguments', () {
      test('returns base URL', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build();
        expect(uri.toString(), equals('https://api.example.com'));
      });

      test('returns base URL with path', () {
        final builder = UrlBuilder('https://api.example.com/v1');
        final uri = builder.build();
        expect(uri.toString(), equals('https://api.example.com/v1'));
      });
    });

    group('toString', () {
      test('returns descriptive string', () {
        final builder = UrlBuilder('https://api.example.com');
        expect(
          builder.toString(),
          equals('UrlBuilder(https://api.example.com)'),
        );
      });
    });

    group('edge cases', () {
      test('handles localhost with port', () {
        final builder = UrlBuilder('http://localhost:8000/api');
        final uri = builder.build(
          pathSegments: ['rooms', '1'],
          queryParameters: {'include': 'threads'},
        );
        expect(uri.host, equals('localhost'));
        expect(uri.port, equals(8000));
        expect(uri.path, equals('/api/rooms/1'));
        expect(uri.queryParameters['include'], equals('threads'));
      });

      test('handles URL-encoded path segments', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri =
            builder.build(pathSegments: ['users', 'john%40example.com']);
        // The segment should be preserved as-is by Uri
        expect(uri.pathSegments.last, contains('john'));
      });

      test('handles numeric path segments', () {
        final builder = UrlBuilder('https://api.example.com');
        final uri = builder.build(pathSegments: ['rooms', '123', 'run', '456']);
        expect(
          uri.toString(),
          equals('https://api.example.com/rooms/123/run/456'),
        );
      });
    });
  });
}
