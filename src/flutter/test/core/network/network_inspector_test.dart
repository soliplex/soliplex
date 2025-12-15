import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/core/network/network_inspector.dart';
import 'package:soliplex/core/network/network_inspector_models.dart';

void main() {
  group('NetworkInspector', () {
    late NetworkInspector inspector;

    setUp(() {
      inspector = NetworkInspector(maxEntries: 10);
    });

    tearDown(() {
      inspector.dispose();
    });

    group('recordRequest', () {
      test('creates entry and returns ID', () {
        final id = inspector.recordRequest(
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {'Content-Type': 'application/json'},
          body: {'key': 'value'},
        );

        expect(id, isNotEmpty);
        expect(inspector.entryCount, equals(1));
      });

      test('generates unique IDs', () {
        final id1 = inspector.recordRequest(
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test1'),
          headers: {},
        );
        final id2 = inspector.recordRequest(
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test2'),
          headers: {},
        );

        expect(id1, isNot(equals(id2)));
      });

      test('entry is accessible after recording', () {
        final id = inspector.recordRequest(
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {'Authorization': 'Bearer token'},
          body: 'request body',
        );

        final entry = inspector.getEntry(id);
        expect(entry, isNotNull);
        expect(entry!.method, equals('POST'));
        expect(entry.fullUrl, equals('https://example.com/api/test'));
        expect(entry.requestHeaders['Authorization'], equals('Bearer token'));
        expect(entry.requestBody, equals('request body'));
        expect(entry.isInFlight, isTrue);
      });

      test('notifies listeners', () {
        var notified = false;
        inspector.addListener(() => notified = true);

        inspector.recordRequest(
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        );

        expect(notified, isTrue);
      });

      test('emits update on stream', () async {
        final updates = <NetworkEntry>[];
        final subscription = inspector.updates.listen(updates.add);

        inspector.recordRequest(
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        );

        await Future<void>.delayed(Duration.zero);
        await subscription.cancel();

        expect(updates.length, equals(1));
        expect(updates.first.method, equals('GET'));
      });
    });

    group('recordResponse', () {
      test('updates existing entry with response', () {
        final requestId = inspector.recordRequest(
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        );

        inspector.recordResponse(
          requestId: requestId,
          statusCode: 200,
          headers: {'Content-Type': 'application/json'},
          body: {'result': 'success'},
        );

        final entry = inspector.getEntry(requestId);
        expect(entry, isNotNull);
        expect(entry!.statusCode, equals(200));
        expect(
          entry.responseHeaders!['Content-Type'],
          equals('application/json'),
        );
        expect(entry.responseBody, equals({'result': 'success'}));
        expect(entry.isComplete, isTrue);
        expect(entry.isSuccess, isTrue);
      });

      test('ignores unknown requestId', () {
        inspector.recordResponse(
          requestId: 'unknown-id',
          statusCode: 200,
          headers: {},
        );

        expect(inspector.entryCount, equals(0));
      });

      test('notifies listeners', () {
        final requestId = inspector.recordRequest(
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        );

        var notifyCount = 0;
        inspector.addListener(() => notifyCount++);

        inspector.recordResponse(
          requestId: requestId,
          statusCode: 200,
          headers: {},
        );

        expect(notifyCount, equals(1));
      });

      test('emits update on stream', () async {
        final requestId = inspector.recordRequest(
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        );

        final updates = <NetworkEntry>[];
        final subscription = inspector.updates.listen(updates.add);

        inspector.recordResponse(
          requestId: requestId,
          statusCode: 200,
          headers: {},
        );

        await Future<void>.delayed(Duration.zero);
        await subscription.cancel();

        expect(updates.length, equals(1));
        expect(updates.first.statusCode, equals(200));
      });
    });

    group('recordError', () {
      test('updates existing entry with error', () {
        final requestId = inspector.recordRequest(
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        );

        inspector.recordError(
          requestId: requestId,
          error: 'Connection refused',
        );

        final entry = inspector.getEntry(requestId);
        expect(entry, isNotNull);
        expect(entry!.error, equals('Connection refused'));
        expect(entry.isComplete, isTrue);
        expect(entry.isError, isTrue);
        expect(entry.statusCode, isNull);
      });

      test('ignores unknown requestId', () {
        inspector.recordError(requestId: 'unknown-id', error: 'Some error');

        expect(inspector.entryCount, equals(0));
      });

      test('notifies listeners', () {
        final requestId = inspector.recordRequest(
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        );

        var notifyCount = 0;
        inspector.addListener(() => notifyCount++);

        inspector.recordError(requestId: requestId, error: 'Network error');

        expect(notifyCount, equals(1));
      });
    });

    group('entries', () {
      test('returns entries in reverse order (newest first)', () {
        inspector.recordRequest(
          method: 'GET',
          uri: Uri.parse('https://example.com/api/first'),
          headers: {},
        );
        inspector.recordRequest(
          method: 'GET',
          uri: Uri.parse('https://example.com/api/second'),
          headers: {},
        );
        inspector.recordRequest(
          method: 'GET',
          uri: Uri.parse('https://example.com/api/third'),
          headers: {},
        );

        final entries = inspector.entries;
        expect(entries.length, equals(3));
        expect(entries[0].fullUrl, contains('third'));
        expect(entries[1].fullUrl, contains('second'));
        expect(entries[2].fullUrl, contains('first'));
      });

      test('returns unmodifiable list', () {
        inspector.recordRequest(
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        );

        final entries = inspector.entries;
        expect(
          () => entries.add(
            NetworkEntry.request(
              id: 'fake',
              method: 'GET',
              uri: Uri.parse('https://example.com'),
              headers: {},
            ),
          ),
          throwsA(isA<UnsupportedError>()),
        );
      });
    });

    group('maxEntries eviction', () {
      test('evicts oldest entries when at capacity', () {
        // Inspector has maxEntries: 10
        for (var i = 0; i < 15; i++) {
          inspector.recordRequest(
            method: 'GET',
            uri: Uri.parse('https://example.com/api/request$i'),
            headers: {},
          );
        }

        expect(inspector.entryCount, equals(10));

        // Should have entries 5-14 (newest 10)
        final entries = inspector.entries;
        expect(entries.first.fullUrl, contains('request14'));
        expect(entries.last.fullUrl, contains('request5'));
      });

      test('evicted entries are no longer accessible by ID', () {
        final evictedId = inspector.recordRequest(
          method: 'GET',
          uri: Uri.parse('https://example.com/api/first'),
          headers: {},
        );

        // Fill up to trigger eviction
        for (var i = 0; i < 15; i++) {
          inspector.recordRequest(
            method: 'GET',
            uri: Uri.parse('https://example.com/api/request$i'),
            headers: {},
          );
        }

        expect(inspector.getEntry(evictedId), isNull);
      });

      test('can still update recently recorded entries after eviction', () {
        // Record first entry
        inspector.recordRequest(
          method: 'GET',
          uri: Uri.parse('https://example.com/api/first'),
          headers: {},
        );

        // Record more entries (but not enough to evict first)
        for (var i = 0; i < 5; i++) {
          inspector.recordRequest(
            method: 'GET',
            uri: Uri.parse('https://example.com/api/request$i'),
            headers: {},
          );
        }

        // Record a tracked entry
        final trackedId = inspector.recordRequest(
          method: 'POST',
          uri: Uri.parse('https://example.com/api/tracked'),
          headers: {},
        );

        // Fill up more to trigger eviction of first entry
        for (var i = 0; i < 5; i++) {
          inspector.recordRequest(
            method: 'GET',
            uri: Uri.parse('https://example.com/api/more$i'),
            headers: {},
          );
        }

        // Tracked entry should still be updatable
        inspector.recordResponse(
          requestId: trackedId,
          statusCode: 200,
          headers: {},
        );

        final entry = inspector.getEntry(trackedId);
        expect(entry, isNotNull);
        expect(entry!.statusCode, equals(200));
      });
    });

    group('clear', () {
      test('removes all entries', () {
        for (var i = 0; i < 5; i++) {
          inspector.recordRequest(
            method: 'GET',
            uri: Uri.parse('https://example.com/api/request$i'),
            headers: {},
          );
        }

        expect(inspector.entryCount, equals(5));

        inspector.clear();

        expect(inspector.entryCount, equals(0));
        expect(inspector.entries, isEmpty);
      });

      test('notifies listeners', () {
        inspector.recordRequest(
          method: 'GET',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        );

        var notified = false;
        inspector.addListener(() => notified = true);

        inspector.clear();

        expect(notified, isTrue);
      });
    });

    group('getEntry', () {
      test('returns entry by ID', () {
        final id = inspector.recordRequest(
          method: 'POST',
          uri: Uri.parse('https://example.com/api/test'),
          headers: {},
        );

        final entry = inspector.getEntry(id);
        expect(entry, isNotNull);
        expect(entry!.id, equals(id));
      });

      test('returns null for unknown ID', () {
        expect(inspector.getEntry('unknown-id'), isNull);
      });
    });

    group('filter', () {
      setUp(() {
        // Set up test data
        inspector.recordRequest(
          method: 'GET',
          uri: Uri.parse('https://example.com/api/users'),
          headers: {},
        );
        final postId = inspector.recordRequest(
          method: 'POST',
          uri: Uri.parse('https://example.com/api/users'),
          headers: {},
        );
        inspector.recordResponse(
          requestId: postId,
          statusCode: 201,
          headers: {},
        );

        final deleteId = inspector.recordRequest(
          method: 'DELETE',
          uri: Uri.parse('https://example.com/api/users/123'),
          headers: {},
        );
        inspector.recordResponse(
          requestId: deleteId,
          statusCode: 404,
          headers: {},
        );

        final errorId = inspector.recordRequest(
          method: 'GET',
          uri: Uri.parse('https://example.com/api/health'),
          headers: {},
        );
        inspector.recordError(requestId: errorId, error: 'Timeout');
      });

      test('filters by method', () {
        final getRequests = inspector.filter(method: 'GET');
        expect(getRequests.length, equals(2));
        expect(getRequests.every((e) => e.method == 'GET'), isTrue);
      });

      test('filters by URL pattern', () {
        final userRequests = inspector.filter(urlPattern: '/users');
        expect(userRequests.length, equals(3));
        expect(userRequests.every((e) => e.fullUrl.contains('/users')), isTrue);
      });

      test('filters by minimum status code', () {
        final clientErrors = inspector.filter(minStatusCode: 400);
        expect(clientErrors.length, equals(1));
        expect(clientErrors.first.statusCode, equals(404));
      });

      test('filters by maximum status code', () {
        final successOnly = inspector.filter(maxStatusCode: 299);
        expect(successOnly.length, equals(1));
        expect(successOnly.first.statusCode, equals(201));
      });

      test('filters by status code range', () {
        final allSuccess = inspector.filter(
          minStatusCode: 200,
          maxStatusCode: 299,
        );
        expect(allSuccess.length, equals(1));
        expect(allSuccess.first.statusCode, equals(201));
      });

      test('filters only errors', () {
        final errors = inspector.filter(onlyErrors: true);
        expect(errors.length, equals(2)); // 404 and network error
        expect(errors.every((e) => e.isError), isTrue);
      });

      test('filters only in-flight', () {
        final inFlight = inspector.filter(onlyInFlight: true);
        expect(inFlight.length, equals(1));
        expect(inFlight.every((e) => e.isInFlight), isTrue);
      });

      test('combines multiple filters', () {
        final result = inspector.filter(method: 'GET', onlyErrors: true);
        expect(result.length, equals(1));
        expect(result.first.method, equals('GET'));
        expect(result.first.error, equals('Timeout'));
      });
    });

    group('dispose', () {
      test('closes update stream', () async {
        // Create a separate inspector for this test to avoid conflict with
        // tearDown
        final disposableInspector = NetworkInspector(maxEntries: 10);

        final completer = Completer<void>();
        disposableInspector.updates.listen((_) {}, onDone: completer.complete);

        disposableInspector.dispose();

        await expectLater(completer.future, completes);
      });
    });
  });
}
