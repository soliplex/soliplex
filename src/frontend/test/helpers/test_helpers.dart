import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/models/active_run_state.dart';
import 'package:soliplex_frontend/core/providers/active_run_notifier.dart';

/// Mock SoliplexApi for testing.
class MockSoliplexApi extends Mock implements SoliplexApi {}

/// Mock ActiveRunNotifier for testing.
///
/// Allows overriding activeRunNotifierProvider with a fixed state.
class MockActiveRunNotifier extends ActiveRunNotifier {
  /// Creates a mock notifier with an initial state.
  MockActiveRunNotifier({required ActiveRunState initialState})
      : super(
          transport: MockHttpTransport(),
          urlBuilder: UrlBuilder('https://example.com'),
        ) {
    state = initialState;
  }
}

/// Mock HttpTransport for testing with mocktail.
class MockHttpTransport extends Mock implements HttpTransport {}

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

/// Creates an ActiveRunNotifier for testing.
ActiveRunNotifier createTestActiveRunNotifier() {
  return ActiveRunNotifier(
    transport: FakeHttpTransport(),
    urlBuilder: FakeUrlBuilder(),
  );
}

/// Test data factory for creating mock objects.
class TestData {
  const TestData._();

  static Room createRoom({
    String id = 'test-room',
    String name = 'Test Room',
    String? description,
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
    String? name,
  }) {
    return ThreadInfo(
      id: id,
      roomId: roomId,
      name: name,
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
}

/// Helper to create a testable app with provider overrides.
Widget createTestApp({
  required Widget home,
  List<Override> overrides = const [],
}) {
  return ProviderScope(
    overrides: overrides,
    child: MaterialApp(home: home),
  );
}
