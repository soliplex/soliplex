import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:soliplex_flutter/client/client.dart';

// Type aliases to match the actual client
typedef OnEvent = void Function(ag_ui.BaseEvent event);
typedef CanvasCallback = void Function(Map<String, dynamic> data);
typedef ContextCallback =
    void Function(String type, {String? summary, Map<String, dynamic>? data});
typedef ActivityCallback = void Function(bool isActive);

/// Mock implementation of SoliplexClient for testing.
class MockSoliplexClient implements SoliplexClient {
  bool getRoomsCalled = false;
  bool getRoomCalled = false;
  bool getThreadsCalled = false;
  bool getThreadCalled = false;
  bool createThreadCalled = false;
  bool deleteThreadCalled = false;
  bool getMessagesCalled = false;
  bool getMessageStreamCalled = false;
  bool chatCalled = false;
  bool cancelRunCalled = false;
  bool disposeCalled = false;

  @override
  String get baseUrl => 'http://localhost:8000';

  @override
  Future<List<Room>> getRooms() async {
    getRoomsCalled = true;
    return [
      Room(
        id: 'room1',
        name: 'Test Room 1',
        description: 'Test room description',
      ),
      Room(
        id: 'room2',
        name: 'Test Room 2',
        description: 'Another test room',
      ),
    ];
  }

  @override
  Future<Room> getRoom(String roomId) async {
    getRoomCalled = true;
    return Room(
      id: roomId,
      name: 'Test Room',
      description: 'Test room description',
    );
  }

  @override
  Future<List<ThreadInfo>> getThreads(String roomId) async {
    getThreadsCalled = true;
    return [
      ThreadInfo(
        id: 'thread1',
        roomId: roomId,
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
      ),
      ThreadInfo(
        id: 'thread2',
        roomId: roomId,
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
      ),
    ];
  }

  @override
  Future<ThreadInfo> getThread(String roomId, String threadId) async {
    getThreadCalled = true;
    return ThreadInfo(
      id: threadId,
      roomId: roomId,
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
    );
  }

  @override
  Future<({String threadId, String runId})> createThread(String roomId) async {
    createThreadCalled = true;
    return (threadId: 'new-thread-id', runId: 'new-run-id');
  }

  @override
  Future<void> deleteThread(String roomId, String threadId) async {
    deleteThreadCalled = true;
  }

  @override
  List<ChatMessage> getMessages(String roomId) {
    getMessagesCalled = true;
    return [
      ChatMessage.text(
        user: ChatUser.user,
        text: 'Hello',
      ),
      ChatMessage.text(
        user: ChatUser.assistant,
        text: 'Hi there!',
      ),
    ];
  }

  @override
  Stream<List<ChatMessage>> getMessageStream(String roomId) {
    getMessageStreamCalled = true;
    return Stream.value([
      ChatMessage.text(
        user: ChatUser.user,
        text: 'Hello',
      ),
      ChatMessage.text(
        user: ChatUser.assistant,
        text: 'Hi there!',
      ),
    ]);
  }

  @override
  Future<void> chat({
    required String roomId,
    required String userMessage,
    Map<String, ag_ui.Tool>? tools,
    Map<String, ToolExecutor>? toolExecutors,
    UiToolHandler? uiToolHandler,
    OnEvent? onEvent,
    CanvasCallback? onCanvasUpdate,
    ContextCallback? onContextUpdate,
    ActivityCallback? onActivityUpdate,
    Map<String, dynamic>? state,
  }) async {
    chatCalled = true;
    // Simulate canvas update
    onCanvasUpdate?.call({'test': 'data'});
    // Simulate context update
    onContextUpdate?.call('test_context', summary: 'Test summary');
    // Simulate activity updates
    onActivityUpdate?.call(true);
    await Future.delayed(Duration(milliseconds: 10));
    onActivityUpdate?.call(false);
  }

  @override
  void cancelRun(String roomId) {
    cancelRunCalled = true;
  }

  @override
  void dispose() {
    disposeCalled = true;
  }

  @override
  SoliplexApi get api => throw UnimplementedError();

  @override
  ConnectionManager get connectionManager => throw UnimplementedError();

  @override
  UrlBuilder get urlBuilder => throw UnimplementedError();

  @override
  void configure(String baseUrl, {Map<String, String>? headers}) {
    // Not implemented in mock
  }

  @override
  Future<RunInfo> getRun(String roomId, String threadId, String runId) async {
    throw UnimplementedError();
  }

  bool createRunCalled = false;
  bool setThreadMetaCalled = false;
  bool setRunMetaCalled = false;

  @override
  Future<String> createRun(String roomId, String threadId) async {
    createRunCalled = true;
    return 'new-run-id';
  }

  @override
  Future<void> setThreadMeta(
    String roomId,
    String threadId, {
    String? name,
    String? description,
  }) async {
    setThreadMetaCalled = true;
  }

  @override
  Future<void> setRunMeta(
    String roomId,
    String threadId,
    String runId, {
    String? label,
  }) async {
    setRunMetaCalled = true;
  }

  @override
  void switchRoom(String roomId) {
    // Not implemented in mock
  }
}
