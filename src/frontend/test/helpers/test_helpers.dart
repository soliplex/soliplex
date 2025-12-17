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
      : super(transport: MockHttpTransport()) {
    state = initialState;
  }
}

/// Mock HttpTransport for testing.
class MockHttpTransport extends Mock implements HttpTransport {}

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

  static ChatMessage createMessage({
    String id = 'test-message',
    ChatUser user = ChatUser.user,
    String text = 'Test message',
    bool isStreaming = false,
  }) {
    return ChatMessage.text(
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
