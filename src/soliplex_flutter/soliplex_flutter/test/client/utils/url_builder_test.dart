import 'package:soliplex_flutter/client/utils/url_builder.dart';
import 'package:test/test.dart';

void main() {
  group('UrlBuilder', () {
    group('normalizeBaseUrl', () {
      test('adds https if no scheme', () {
        expect(
          UrlBuilder.normalizeBaseUrl('example.com'),
          'https://example.com',
        );
      });

      test('preserves http scheme', () {
        expect(
          UrlBuilder.normalizeBaseUrl('http://localhost:8000'),
          'http://localhost:8000',
        );
      });

      test('preserves https scheme', () {
        expect(
          UrlBuilder.normalizeBaseUrl('https://example.com'),
          'https://example.com',
        );
      });

      test('removes trailing slash', () {
        expect(
          UrlBuilder.normalizeBaseUrl('https://example.com/'),
          'https://example.com',
        );
      });

      test('removes multiple trailing slashes', () {
        expect(
          UrlBuilder.normalizeBaseUrl('https://example.com///'),
          'https://example.com',
        );
      });

      test('removes /api suffix', () {
        expect(
          UrlBuilder.normalizeBaseUrl('https://example.com/api'),
          'https://example.com',
        );
      });

      test('removes /api/ suffix', () {
        expect(
          UrlBuilder.normalizeBaseUrl('https://example.com/api/'),
          'https://example.com',
        );
      });

      test('trims whitespace', () {
        expect(
          UrlBuilder.normalizeBaseUrl('  https://example.com  '),
          'https://example.com',
        );
      });
    });

    group('URL building', () {
      late UrlBuilder builder;

      setUp(() {
        builder = UrlBuilder('http://localhost:8000');
      });

      test('serverUrl returns base URL', () {
        expect(builder.serverUrl, 'http://localhost:8000');
      });

      test('apiBaseUrl returns base URL with /api', () {
        expect(builder.apiBaseUrl, 'http://localhost:8000/api');
      });

      test('rooms returns correct URI', () {
        expect(
          builder.rooms().toString(),
          'http://localhost:8000/api/v1/rooms',
        );
      });

      test('room returns correct URI', () {
        expect(
          builder.room('room-1').toString(),
          'http://localhost:8000/api/v1/rooms/room-1',
        );
      });

      test('threads returns correct URI', () {
        expect(
          builder.threads('room-1').toString(),
          'http://localhost:8000/api/v1/rooms/room-1/agui',
        );
      });

      test('thread returns correct URI', () {
        expect(
          builder.thread('room-1', 'thread-1').toString(),
          'http://localhost:8000/api/v1/rooms/room-1/agui/thread-1',
        );
      });

      test('threadMeta returns correct URI', () {
        expect(
          builder.threadMeta('room-1', 'thread-1').toString(),
          'http://localhost:8000/api/v1/rooms/room-1/agui/thread-1/meta',
        );
      });

      test('run returns correct URI', () {
        expect(
          builder.run('room-1', 'thread-1', 'run-1').toString(),
          'http://localhost:8000/api/v1/rooms/room-1/agui/thread-1/run-1',
        );
      });

      test('runMeta returns correct URI', () {
        expect(
          builder.runMeta('room-1', 'thread-1', 'run-1').toString(),
          'http://localhost:8000/api/v1/rooms/room-1/agui/thread-1/run-1/meta',
        );
      });

      test('runEndpointPath returns relative path without leading slash', () {
        // AG-UI client adds the leading slash when constructing the URL
        expect(
          builder.runEndpointPath('room-1', 'thread-1', 'run-1'),
          'api/v1/rooms/room-1/agui/thread-1/run-1',
        );
      });
    });
  });
}
