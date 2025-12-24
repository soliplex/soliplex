import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
// ignore: implementation_imports, depend_on_referenced_packages
import 'package:riverpod/src/framework.dart' show Override;
// Hide ag_ui's CancelToken - HttpTransport uses our local one.
import 'package:soliplex_client/soliplex_client.dart' hide CancelToken;
import 'package:soliplex_client/src/utils/cancel_token.dart';
import 'package:soliplex_frontend/core/models/active_run_state.dart';
import 'package:soliplex_frontend/core/models/app_config.dart';
import 'package:soliplex_frontend/core/providers/active_run_notifier.dart';
import 'package:soliplex_frontend/core/providers/active_run_provider.dart';
import 'package:soliplex_frontend/core/providers/config_provider.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';

/// Mock SoliplexApi for testing.
class MockSoliplexApi extends Mock implements SoliplexApi {}

/// Mock ActiveRunNotifier for testing.
///
/// Allows overriding activeRunNotifierProvider with a fixed state.
class MockActiveRunNotifier extends Notifier<ActiveRunState>
    implements ActiveRunNotifier {
  /// Creates a mock notifier with an initial state.
  MockActiveRunNotifier({required this.initialState});

  final ActiveRunState initialState;

  @override
  ActiveRunState build() => initialState;

  @override
  Future<void> startRun({
    required String roomId,
    required String threadId,
    required String userMessage,
    String? existingRunId,
    Map<String, dynamic>? initialState,
  }) async {}

  @override
  Future<void> cancelRun() async {}

  @override
  void reset() {}
}

/// Creates an override for activeRunNotifierProvider with a mock state.
Override activeRunNotifierOverride(ActiveRunState mockState) {
  return activeRunNotifierProvider
      .overrideWith(() => MockActiveRunNotifier(initialState: mockState));
}

/// Mock ConfigNotifier for testing.
class MockConfigNotifier extends Notifier<AppConfig> implements ConfigNotifier {
  MockConfigNotifier({required this.initialConfig});

  final AppConfig initialConfig;

  @override
  AppConfig build() => initialConfig;

  @override
  void set(AppConfig value) => state = value;
}

/// Creates an override for configProvider with a mock config.
Override configProviderOverride(AppConfig config) {
  return configProvider
      .overrideWith(() => MockConfigNotifier(initialConfig: config));
}

/// Mock CurrentRoomIdNotifier for testing.
class MockCurrentRoomIdNotifier extends Notifier<String?>
    implements CurrentRoomIdNotifier {
  MockCurrentRoomIdNotifier({this.initialRoomId});

  final String? initialRoomId;

  @override
  String? build() => initialRoomId;

  @override
  void set(String? value) => state = value;
}

/// Creates an override for currentRoomIdProvider with a mock room ID.
Override currentRoomIdProviderOverride(String? roomId) {
  return currentRoomIdProvider
      .overrideWith(() => MockCurrentRoomIdNotifier(initialRoomId: roomId));
}

/// Mock ThreadSelectionNotifier for testing.
class MockThreadSelectionNotifier extends Notifier<ThreadSelection>
    implements ThreadSelectionNotifier {
  MockThreadSelectionNotifier({required this.initialSelection});

  final ThreadSelection initialSelection;

  @override
  ThreadSelection build() => initialSelection;

  @override
  void set(ThreadSelection value) => state = value;
}

/// Creates an override for threadSelectionProvider with a mock selection.
Override threadSelectionProviderOverride(ThreadSelection selection) {
  return threadSelectionProvider.overrideWith(
    () => MockThreadSelectionNotifier(initialSelection: selection),
  );
}

/// Mock HttpTransport for testing with mocktail.
class MockHttpTransport extends Mock implements HttpTransport {}

/// Mock AgUiClient for testing with mocktail.
class MockAgUiClient extends Mock implements AgUiClient {}

/// Fake HttpTransport for testing without mocktail.
class FakeHttpTransport implements HttpTransport {
  @override
  Duration get defaultTimeout => const Duration(seconds: 30);

  @override
  Future<T> request<T>(
    String method,
    Uri uri, {
    Object? body,
    Map<String, String>? headers,
    Duration? timeout,
    CancelToken? cancelToken,
    T Function(Map<String, dynamic>)? fromJson,
  }) async {
    return null as T;
  }

  @override
  Stream<List<int>> requestStream(
    String method,
    Uri uri, {
    Object? body,
    Map<String, String>? headers,
    CancelToken? cancelToken,
  }) async* {
    yield [];
  }

  @override
  void close() {}
}

/// Fake UrlBuilder for testing.
class FakeUrlBuilder implements UrlBuilder {
  @override
  String get baseUrl => 'http://localhost';

  @override
  Uri build({
    String? path,
    List<String>? pathSegments,
    Map<String, String>? queryParameters,
  }) =>
      Uri.parse('http://localhost/${path ?? ''}');
}

/// Test data factory for creating mock objects.
class TestData {
  const TestData._();

  static DateTime _defaultTimestamp(DateTime? t) => t ?? DateTime.now();

  static Room createRoom({
    String id = 'test-room',
    String name = 'Test Room',
    String description = '',
  }) {
    return Room(
      id: id,
      name: name,
      description: description,
    );
  }

  static ThreadInfo createThread({
    String id = 'test-thread',
    String roomId = 'test-room',
    String name = '',
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    final now = DateTime.now();
    return ThreadInfo(
      id: id,
      roomId: roomId,
      name: name,
      createdAt: createdAt ?? now,
      updatedAt: updatedAt ?? now,
    );
  }

  static TextMessage createMessage({
    String id = 'test-message',
    ChatUser user = ChatUser.user,
    String text = 'Test message',
    bool isStreaming = false,
  }) {
    return TextMessage.create(
      id: id,
      user: user,
      text: text,
      isStreaming: isStreaming,
    );
  }

  static HttpRequestEvent createRequestEvent({
    String requestId = 'req-1',
    DateTime? timestamp,
    String method = 'GET',
    Uri? uri,
    Map<String, String> headers = const {},
  }) {
    return HttpRequestEvent(
      requestId: requestId,
      timestamp: _defaultTimestamp(timestamp),
      method: method,
      uri: uri ?? Uri.parse('http://localhost/api/v1/rooms'),
      headers: headers,
    );
  }

  static HttpResponseEvent createResponseEvent({
    String requestId = 'req-1',
    DateTime? timestamp,
    int statusCode = 200,
    Duration duration = const Duration(milliseconds: 45),
    int bodySize = 1234,
    String? reasonPhrase,
  }) {
    return HttpResponseEvent(
      requestId: requestId,
      timestamp: _defaultTimestamp(timestamp),
      statusCode: statusCode,
      duration: duration,
      bodySize: bodySize,
      reasonPhrase: reasonPhrase,
    );
  }

  static HttpErrorEvent createErrorEvent({
    String requestId = 'req-1',
    DateTime? timestamp,
    String method = 'POST',
    Uri? uri,
    SoliplexException? exception,
    Duration duration = const Duration(seconds: 2),
  }) {
    return HttpErrorEvent(
      requestId: requestId,
      timestamp: _defaultTimestamp(timestamp),
      method: method,
      uri: uri ?? Uri.parse('http://localhost/api/v1/threads'),
      exception:
          exception ?? const NetworkException(message: 'Connection failed'),
      duration: duration,
    );
  }

  static HttpStreamStartEvent createStreamStartEvent({
    String requestId = 'req-1',
    DateTime? timestamp,
    String method = 'GET',
    Uri? uri,
  }) {
    return HttpStreamStartEvent(
      requestId: requestId,
      timestamp: _defaultTimestamp(timestamp),
      method: method,
      uri: uri ?? Uri.parse('http://localhost/api/v1/runs/run-1/stream'),
    );
  }

  static HttpStreamEndEvent createStreamEndEvent({
    String requestId = 'req-1',
    DateTime? timestamp,
    int bytesReceived = 5200,
    Duration duration = const Duration(seconds: 10),
    SoliplexException? error,
  }) {
    return HttpStreamEndEvent(
      requestId: requestId,
      timestamp: _defaultTimestamp(timestamp),
      bytesReceived: bytesReceived,
      duration: duration,
      error: error,
    );
  }
}

/// Helper to create a testable app with provider overrides.
Widget createTestApp({
  required Widget home,
  // Using dynamic list since Override type is internal in Riverpod 3.0
  List<dynamic> overrides = const [],
}) {
  return ProviderScope(
    overrides: overrides.cast(),
    child: MaterialApp(home: home),
  );
}
