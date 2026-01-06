import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mocktail/mocktail.dart';
// Riverpod 3.0 doesn't export Override from a public location.
// Using dynamic list + cast in createTestApp() avoids this import,
// but helper functions need the type for signatures.
// ignore: implementation_imports, depend_on_referenced_packages
import 'package:riverpod/src/framework.dart' show Override;
// Hide ag_ui's CancelToken - HttpTransport uses our local one.
import 'package:soliplex_client/soliplex_client.dart' hide CancelToken;
import 'package:soliplex_client/src/utils/cancel_token.dart';
import 'package:soliplex_frontend/core/auth/auth_provider.dart';
import 'package:soliplex_frontend/core/auth/auth_state.dart';
import 'package:soliplex_frontend/core/auth/auth_storage.dart';
import 'package:soliplex_frontend/core/models/active_run_state.dart';
import 'package:soliplex_frontend/core/models/app_config.dart';
import 'package:soliplex_frontend/core/providers/active_run_notifier.dart';
import 'package:soliplex_frontend/core/providers/active_run_provider.dart';
import 'package:soliplex_frontend/core/providers/config_provider.dart';
import 'package:soliplex_frontend/core/providers/rooms_provider.dart';
import 'package:soliplex_frontend/core/providers/threads_provider.dart';

/// Mock AuthStorage for testing.
class MockAuthStorage extends Mock implements AuthStorage {}

/// Mock TokenRefreshService for testing.
class MockTokenRefreshService extends Mock implements TokenRefreshService {}

/// Creates mocked auth dependencies and their provider overrides.
///
/// Returns a record with:
/// - `overrides`: Provider overrides for [authStorageProvider] and
///   [tokenRefreshServiceProvider]
/// - `storage`: The [MockAuthStorage] instance for stubbing
/// - `refreshService`: The [MockTokenRefreshService] instance for stubbing
///
/// The mock storage is configured to return null from `loadTokens()` by
/// default (unauthenticated state).
///
/// Use with [ProviderContainer] or [createContainerWithMockedAuth]:
/// ```dart
/// final mocks = createMockedAuthDependencies();
/// final container = ProviderContainer(overrides: mocks.overrides);
/// when(() => mocks.storage.loadTokens()).thenAnswer((_) async => tokens);
/// ```
({
  List<Override> overrides,
  MockAuthStorage storage,
  MockTokenRefreshService refreshService,
}) createMockedAuthDependencies() {
  final storage = MockAuthStorage();
  final refreshService = MockTokenRefreshService();

  when(storage.loadTokens).thenAnswer((_) async => null);

  return (
    overrides: [
      authStorageProvider.overrideWithValue(storage),
      tokenRefreshServiceProvider.overrideWithValue(refreshService),
    ],
    storage: storage,
    refreshService: refreshService,
  );
}

/// Creates a [ProviderContainer] with mocked auth providers.
///
/// Convenience wrapper around [createMockedAuthDependencies] for tests that
/// need auth mocking but don't need direct access to the mocks.
ProviderContainer createContainerWithMockedAuth({
  List<Override> overrides = const [],
}) {
  final authMocks = createMockedAuthDependencies();
  return ProviderContainer(
    overrides: [
      ...authMocks.overrides,
      ...overrides,
    ],
  );
}

/// Waits for the auth provider to finish restoring session.
///
/// Auth restoration is fire-and-forget from `build()`, so tests need to wait
/// for it to complete. Uses Riverpod's listener to await state changes
/// rather than polling.
Future<void> waitForAuthRestore(ProviderContainer container) async {
  // Check if already complete
  final currentState = container.read(authProvider);
  if (currentState is! AuthLoading) return;

  // Listen for state change
  final completer = Completer<void>();
  final subscription = container.listen(authProvider, (previous, next) {
    if (next is! AuthLoading && !completer.isCompleted) {
      completer.complete();
    }
  });

  try {
    await completer.future.timeout(const Duration(seconds: 5));
  } finally {
    subscription.close();
  }
}

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

  /// Creates an Authenticated state for auth testing.
  ///
  /// By default creates valid (non-expired) tokens. Use [expired] parameter
  /// to create tokens that expired 1 hour ago.
  static Authenticated createAuthenticated({
    bool expired = false,
    String accessToken = 'test-access-token',
    String refreshToken = 'test-refresh-token',
    String issuerId = 'issuer-1',
    String issuerDiscoveryUrl = 'https://idp.example.com/.well-known',
    String clientId = 'client-app',
    String idToken = 'test-id-token',
  }) {
    final expiresAt = expired
        ? DateTime.now().subtract(const Duration(hours: 1))
        : DateTime.now().add(const Duration(hours: 1));

    return Authenticated(
      accessToken: accessToken,
      refreshToken: refreshToken,
      expiresAt: expiresAt,
      issuerId: issuerId,
      issuerDiscoveryUrl: issuerDiscoveryUrl,
      clientId: clientId,
      idToken: idToken,
    );
  }
}

/// Helper to create a testable app with provider overrides.
///
/// Wraps the widget in a Scaffold since screens no longer provide their own.
/// The AppShell wrapper in the real app provides the Scaffold.
///
/// [onContainerCreated] is called with the [ProviderContainer] after it's
/// created, allowing tests to read provider state.
Widget createTestApp({
  required Widget home,
  // Using dynamic list since Override type is internal in Riverpod 3.0
  List<dynamic> overrides = const [],
  void Function(ProviderContainer)? onContainerCreated,
}) {
  return UncontrolledProviderScope(
    container: ProviderContainer(overrides: overrides.cast())
      ..also(onContainerCreated),
    child: MaterialApp(home: Scaffold(body: home)),
  );
}

extension _Also<T> on T {
  void also(void Function(T)? action) {
    if (action != null) action(this);
  }
}
