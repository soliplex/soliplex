import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/features/inspector/models/http_event_group.dart';

import '../../../helpers/test_helpers.dart';

void main() {
  group('HttpEventGroup', () {
    group('isStream', () {
      test('returns true when streamStart is present', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
        );
        expect(group.isStream, isTrue);
      });

      test('returns false when no streamStart', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
        );
        expect(group.isStream, isFalse);
      });
    });

    group('methodLabel', () {
      test('returns SSE for streaming requests', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
        );
        expect(group.methodLabel, 'SSE');
      });

      test('returns method for regular requests', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(method: 'POST'),
        );
        expect(group.methodLabel, 'POST');
      });

      test('returns method from error event when no request', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          error: TestData.createErrorEvent(method: 'DELETE'),
        );
        expect(group.methodLabel, 'DELETE');
      });
    });

    group('method', () {
      test('returns method from request event', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(method: 'POST'),
        );
        expect(group.method, 'POST');
      });

      test('returns method from error event when no request', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          error: TestData.createErrorEvent(method: 'DELETE'),
        );
        expect(group.method, 'DELETE');
      });

      test('returns method from streamStart event when no request or error',
          () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
        );
        expect(group.method, 'GET');
      });

      test('prefers request over error', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(method: 'PUT'),
          error: TestData.createErrorEvent(method: 'DELETE'),
        );
        expect(group.method, 'PUT');
      });

      test('throws StateError when no events have method', () {
        final group = HttpEventGroup(requestId: 'req-1');
        expect(() => group.method, throwsStateError);
      });

      test('throws StateError for response-only orphan group', () {
        final group = HttpEventGroup(
          requestId: 'orphan',
          response: TestData.createResponseEvent(requestId: 'orphan'),
        );
        expect(() => group.method, throwsStateError);
      });
    });

    group('uri', () {
      test('returns uri from request event', () {
        final uri = Uri.parse('http://example.com/api');
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(uri: uri),
        );
        expect(group.uri, uri);
      });

      test('returns uri from error event when no request', () {
        final uri = Uri.parse('http://example.com/error');
        final group = HttpEventGroup(
          requestId: 'req-1',
          error: TestData.createErrorEvent(uri: uri),
        );
        expect(group.uri, uri);
      });

      test('returns uri from streamStart event when no request or error', () {
        final uri = Uri.parse('http://example.com/stream');
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(uri: uri),
        );
        expect(group.uri, uri);
      });

      test('throws StateError when no events have uri', () {
        final group = HttpEventGroup(requestId: 'req-1');
        expect(() => group.uri, throwsStateError);
      });

      test('throws StateError for response-only orphan group', () {
        final group = HttpEventGroup(
          requestId: 'orphan',
          response: TestData.createResponseEvent(requestId: 'orphan'),
        );
        expect(() => group.uri, throwsStateError);
      });
    });

    group('pathWithQuery', () {
      test('returns path without query', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(
            uri: Uri.parse('http://localhost/api/rooms'),
          ),
        );
        expect(group.pathWithQuery, '/api/rooms');
      });

      test('returns path with query parameters', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(
            uri: Uri.parse('http://localhost/api/rooms?limit=50&offset=100'),
          ),
        );
        expect(group.pathWithQuery, '/api/rooms?limit=50&offset=100');
      });

      test('returns / for empty path', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(
            uri: Uri.parse('http://localhost'),
          ),
        );
        expect(group.pathWithQuery, '/');
      });

      test('returns / with query for empty path with query', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(
            uri: Uri.parse('http://localhost?foo=bar'),
          ),
        );
        expect(group.pathWithQuery, '/?foo=bar');
      });
    });

    group('timestamp', () {
      test('returns timestamp from request event', () {
        final time = DateTime(2024, 1, 15, 10, 30);
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(timestamp: time),
        );
        expect(group.timestamp, time);
      });

      test('returns timestamp from streamStart when no request', () {
        final time = DateTime(2024, 1, 15, 11);
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(timestamp: time),
        );
        expect(group.timestamp, time);
      });

      test('returns timestamp from error when no request or streamStart', () {
        final time = DateTime(2024, 1, 15, 12);
        final group = HttpEventGroup(
          requestId: 'req-1',
          error: TestData.createErrorEvent(timestamp: time),
        );
        expect(group.timestamp, time);
      });

      test('throws StateError when no events have timestamp', () {
        final group = HttpEventGroup(requestId: 'req-1');
        expect(() => group.timestamp, throwsStateError);
      });
    });

    group('status', () {
      test('returns pending when no response', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
        );
        expect(group.status, HttpEventStatus.pending);
      });

      test('returns success for 200', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(),
        );
        expect(group.status, HttpEventStatus.success);
      });

      test('returns success for 201', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 201),
        );
        expect(group.status, HttpEventStatus.success);
      });

      test('returns success for 204', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 204),
        );
        expect(group.status, HttpEventStatus.success);
      });

      test('returns success for 299 (boundary)', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 299),
        );
        expect(group.status, HttpEventStatus.success);
      });

      test('returns success for 1xx (non-standard)', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 100),
        );
        expect(group.status, HttpEventStatus.success);
      });

      test('returns success for 3xx (non-standard)', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 301),
        );
        expect(group.status, HttpEventStatus.success);
      });

      test('returns clientError for 400', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 400),
        );
        expect(group.status, HttpEventStatus.clientError);
      });

      test('returns clientError for 403', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 403),
        );
        expect(group.status, HttpEventStatus.clientError);
      });

      test('returns clientError for 404', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 404),
        );
        expect(group.status, HttpEventStatus.clientError);
      });

      test('returns clientError for 499 (boundary)', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 499),
        );
        expect(group.status, HttpEventStatus.clientError);
      });

      test('returns serverError for 500', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 500),
        );
        expect(group.status, HttpEventStatus.serverError);
      });

      test('returns serverError for 502', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 502),
        );
        expect(group.status, HttpEventStatus.serverError);
      });

      test('returns serverError for 503', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 503),
        );
        expect(group.status, HttpEventStatus.serverError);
      });

      test('returns networkError when error present', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          error: TestData.createErrorEvent(),
        );
        expect(group.status, HttpEventStatus.networkError);
      });

      test('networkError takes precedence over missing response', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          error: TestData.createErrorEvent(),
        );
        expect(group.status, HttpEventStatus.networkError);
      });

      test('returns streaming when stream started but not ended', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
        );
        expect(group.status, HttpEventStatus.streaming);
      });

      test('returns streamComplete when stream ends without error', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
          streamEnd: TestData.createStreamEndEvent(),
        );
        expect(group.status, HttpEventStatus.streamComplete);
      });

      test('returns streamError when stream ends with error', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
          streamEnd: TestData.createStreamEndEvent(
            error: const NetworkException(message: 'Lost connection'),
          ),
        );
        expect(group.status, HttpEventStatus.streamError);
      });

      test('streaming status takes precedence over response', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
          response: TestData.createResponseEvent(statusCode: 500),
        );
        expect(group.status, HttpEventStatus.streaming);
      });
    });

    group('semanticLabel', () {
      test('describes pending GET request', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(
            uri: Uri.parse('http://localhost/api/rooms'),
          ),
        );
        expect(group.semanticLabel, 'GET request to /api/rooms, pending');
      });

      test('describes successful response', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(
            method: 'POST',
            uri: Uri.parse('http://localhost/api/threads'),
          ),
          response: TestData.createResponseEvent(statusCode: 201),
        );
        expect(
          group.semanticLabel,
          'POST request to /api/threads, success, status 201',
        );
      });

      test('describes client error', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(
            uri: Uri.parse('http://localhost/api/missing'),
          ),
          response: TestData.createResponseEvent(statusCode: 404),
        );
        expect(group.semanticLabel, contains('client error'));
        expect(group.semanticLabel, contains('404'));
      });

      test('describes server error', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(
            uri: Uri.parse('http://localhost/api/error'),
          ),
          response: TestData.createResponseEvent(statusCode: 500),
        );
        expect(group.semanticLabel, contains('server error'));
        expect(group.semanticLabel, contains('500'));
      });

      test('describes network error', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          error: TestData.createErrorEvent(
            exception: const NetworkException(message: 'Timeout'),
          ),
        );
        expect(group.semanticLabel, contains('network error'));
        expect(group.semanticLabel, contains('NetworkException'));
      });

      test('describes SSE streaming', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(
            uri: Uri.parse('http://localhost/api/stream'),
          ),
        );
        expect(group.semanticLabel, 'SSE stream to /api/stream, streaming');
      });

      test('describes completed stream', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(
            uri: Uri.parse('http://localhost/api/stream'),
          ),
          streamEnd: TestData.createStreamEndEvent(),
        );
        expect(
          group.semanticLabel,
          'SSE stream to /api/stream, stream complete',
        );
      });

      test('describes stream error', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(
            uri: Uri.parse('http://localhost/api/stream'),
          ),
          streamEnd: TestData.createStreamEndEvent(
            error: const NetworkException(message: 'Lost'),
          ),
        );
        expect(group.semanticLabel, 'SSE stream to /api/stream, stream error');
      });
    });

    group('hasSpinner', () {
      test('returns true for pending status', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
        );
        expect(group.hasSpinner, isTrue);
      });

      test('returns true for streaming status', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
        );
        expect(group.hasSpinner, isTrue);
      });

      test('returns false for success status', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(),
        );
        expect(group.hasSpinner, isFalse);
      });

      test('returns false for error status', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          error: TestData.createErrorEvent(),
        );
        expect(group.hasSpinner, isFalse);
      });

      test('returns false for streamComplete status', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
          streamEnd: TestData.createStreamEndEvent(),
        );
        expect(group.hasSpinner, isFalse);
      });
    });

    group('hasEvents', () {
      test('returns false when no events', () {
        final group = HttpEventGroup(requestId: 'req-1');
        expect(group.hasEvents, isFalse);
      });

      test('returns true when has request', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
        );
        expect(group.hasEvents, isTrue);
      });

      test('returns true when has response', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          response: TestData.createResponseEvent(),
        );
        expect(group.hasEvents, isTrue);
      });

      test('returns true when has error', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          error: TestData.createErrorEvent(),
        );
        expect(group.hasEvents, isTrue);
      });

      test('returns true when has streamStart', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
        );
        expect(group.hasEvents, isTrue);
      });

      test('returns true when has streamEnd', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamEnd: TestData.createStreamEndEvent(),
        );
        expect(group.hasEvents, isTrue);
      });
    });

    group('statusDescription', () {
      test('returns pending for pending status', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
        );
        expect(group.statusDescription, 'pending');
      });

      test('returns success with status code for success', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 201),
        );
        expect(group.statusDescription, 'success, status 201');
      });

      test('returns client error with status code', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 404),
        );
        expect(group.statusDescription, 'client error, status 404');
      });

      test('returns server error with status code', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: TestData.createRequestEvent(),
          response: TestData.createResponseEvent(statusCode: 500),
        );
        expect(group.statusDescription, 'server error, status 500');
      });

      test('returns network error with exception type', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          error: TestData.createErrorEvent(),
        );
        expect(group.statusDescription, 'network error, NetworkException');
      });

      test('returns streaming for active stream', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
        );
        expect(group.statusDescription, 'streaming');
      });

      test('returns stream complete for completed stream', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
          streamEnd: TestData.createStreamEndEvent(),
        );
        expect(group.statusDescription, 'stream complete');
      });

      test('returns stream error for failed stream', () {
        final group = HttpEventGroup(
          requestId: 'req-1',
          streamStart: TestData.createStreamStartEvent(),
          streamEnd: TestData.createStreamEndEvent(
            error: const NetworkException(message: 'Lost'),
          ),
        );
        expect(group.statusDescription, 'stream error');
      });
    });

    group('copyWith', () {
      test('preserves requestId', () {
        final group = HttpEventGroup(requestId: 'req-1');
        final copy = group.copyWith();
        expect(copy.requestId, 'req-1');
      });

      test('updates request', () {
        final group = HttpEventGroup(requestId: 'req-1');
        final request = TestData.createRequestEvent();
        final copy = group.copyWith(request: request);
        expect(copy.request, request);
      });

      test('updates response', () {
        final group = HttpEventGroup(requestId: 'req-1');
        final response = TestData.createResponseEvent();
        final copy = group.copyWith(response: response);
        expect(copy.response, response);
      });

      test('updates error', () {
        final group = HttpEventGroup(requestId: 'req-1');
        final error = TestData.createErrorEvent();
        final copy = group.copyWith(error: error);
        expect(copy.error, error);
      });

      test('updates streamStart', () {
        final group = HttpEventGroup(requestId: 'req-1');
        final streamStart = TestData.createStreamStartEvent();
        final copy = group.copyWith(streamStart: streamStart);
        expect(copy.streamStart, streamStart);
      });

      test('updates streamEnd', () {
        final group = HttpEventGroup(requestId: 'req-1');
        final streamEnd = TestData.createStreamEndEvent();
        final copy = group.copyWith(streamEnd: streamEnd);
        expect(copy.streamEnd, streamEnd);
      });

      test('preserves existing values when not specified', () {
        final request = TestData.createRequestEvent();
        final response = TestData.createResponseEvent();
        final group = HttpEventGroup(
          requestId: 'req-1',
          request: request,
          response: response,
        );

        final error = TestData.createErrorEvent();
        final copy = group.copyWith(error: error);

        expect(copy.request, request);
        expect(copy.response, response);
        expect(copy.error, error);
      });
    });
  });
}
