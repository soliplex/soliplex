import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_client/soliplex_client.dart';

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
