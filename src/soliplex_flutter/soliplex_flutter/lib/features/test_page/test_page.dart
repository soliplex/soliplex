import 'dart:convert';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../providers/providers.dart';

/// Debug test page for manual client testing.
///
/// Provides interactive controls for testing all API endpoints
/// and viewing live SSE events.
class TestPage extends ConsumerStatefulWidget {
  const TestPage({super.key});

  @override
  ConsumerState<TestPage> createState() => _TestPageState();
}

class _TestPageState extends ConsumerState<TestPage> {
  final _serverUrlController = TextEditingController(text: 'http://localhost:8000');
  final _roomIdController = TextEditingController();
  final _threadIdController = TextEditingController();
  final _runIdController = TextEditingController();
  final _messageController = TextEditingController();
  final _logController = ScrollController();

  final List<_LogEntry> _logs = [];
  bool _isConnected = false;

  @override
  void dispose() {
    _serverUrlController.dispose();
    _roomIdController.dispose();
    _threadIdController.dispose();
    _runIdController.dispose();
    _messageController.dispose();
    _logController.dispose();
    super.dispose();
  }

  void _log(String message, {bool isError = false, bool isEvent = false}) {
    setState(() {
      _logs.add(_LogEntry(
        timestamp: DateTime.now(),
        message: message,
        isError: isError,
        isEvent: isEvent,
      ));
    });
    // Scroll to bottom
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_logController.hasClients) {
        _logController.animateTo(
          _logController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 100),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _clearLogs() {
    setState(() {
      _logs.clear();
    });
  }

  Future<void> _connect() async {
    final url = _serverUrlController.text.trim();
    if (url.isEmpty) {
      _log('Error: Server URL is required', isError: true);
      return;
    }

    try {
      _log('Connecting to $url...');
      final configure = ref.read(configureClientProvider);
      configure(url);
      setState(() {
        _isConnected = true;
      });
      _log('Connected to $url');
    } catch (e) {
      _log('Connection error: $e', isError: true);
    }
  }

  Future<void> _getRooms() async {
    _log('GET /api/v1/rooms');
    try {
      final client = ref.read(soliplexClientProvider);
      final rooms = await client.getRooms();
      _log('Response: ${rooms.length} rooms');
      for (final room in rooms) {
        _log('  - ${room.id}: ${room.name}');
      }
    } catch (e) {
      _log('Error: $e', isError: true);
    }
  }

  Future<void> _getThreads() async {
    final roomId = _roomIdController.text.trim();
    if (roomId.isEmpty) {
      _log('Error: Room ID is required', isError: true);
      return;
    }

    _log('GET /api/v1/rooms/$roomId/agui');
    try {
      final client = ref.read(soliplexClientProvider);
      final threads = await client.getThreads(roomId);
      _log('Response: ${threads.length} threads');
      for (final thread in threads) {
        _log('  - ${thread.id}: ${thread.name ?? "(unnamed)"}');
      }
    } catch (e) {
      _log('Error: $e', isError: true);
    }
  }

  Future<void> _createThread() async {
    final roomId = _roomIdController.text.trim();
    if (roomId.isEmpty) {
      _log('Error: Room ID is required', isError: true);
      return;
    }

    _log('POST /api/v1/rooms/$roomId/agui');
    try {
      final client = ref.read(soliplexClientProvider);
      final result = await client.createThread(roomId);
      _log('Response: thread_id=${result.threadId}, run_id=${result.runId}');
      setState(() {
        _threadIdController.text = result.threadId;
        _runIdController.text = result.runId;
      });
    } catch (e) {
      _log('Error: $e', isError: true);
    }
  }

  Future<void> _deleteThread() async {
    final roomId = _roomIdController.text.trim();
    final threadId = _threadIdController.text.trim();
    if (roomId.isEmpty || threadId.isEmpty) {
      _log('Error: Room ID and Thread ID are required', isError: true);
      return;
    }

    _log('DELETE /api/v1/rooms/$roomId/agui/$threadId');
    try {
      final client = ref.read(soliplexClientProvider);
      await client.deleteThread(roomId, threadId);
      _log('Response: Thread deleted');
      setState(() {
        _threadIdController.clear();
        _runIdController.clear();
      });
    } catch (e) {
      _log('Error: $e', isError: true);
    }
  }

  Future<void> _createRun() async {
    final roomId = _roomIdController.text.trim();
    final threadId = _threadIdController.text.trim();
    if (roomId.isEmpty || threadId.isEmpty) {
      _log('Error: Room ID and Thread ID are required', isError: true);
      return;
    }

    _log('POST /api/v1/rooms/$roomId/agui/$threadId');
    try {
      final client = ref.read(soliplexClientProvider);
      final runId = await client.createRun(roomId, threadId);
      _log('Response: run_id=$runId');
      setState(() {
        _runIdController.text = runId;
      });
    } catch (e) {
      _log('Error: $e', isError: true);
    }
  }

  Future<void> _chat() async {
    final roomId = _roomIdController.text.trim();
    final message = _messageController.text.trim();
    if (roomId.isEmpty || message.isEmpty) {
      _log('Error: Room ID and message are required', isError: true);
      return;
    }

    _log('CHAT: "$message"');
    try {
      final client = ref.read(soliplexClientProvider);
      await client.chat(
        roomId: roomId,
        userMessage: message,
        onEvent: (event) {
          _log('EVENT: ${_formatEvent(event)}', isEvent: true);
        },
        onCanvasUpdate: (data) {
          _log('CANVAS: ${jsonEncode(data)}', isEvent: true);
        },
        onActivityUpdate: (isActive) {
          _log('ACTIVITY: ${isActive ? "active" : "idle"}', isEvent: true);
        },
      );
      _log('Chat completed');
    } catch (e) {
      _log('Error: $e', isError: true);
    }
  }

  String _formatEvent(ag_ui.BaseEvent event) {
    return switch (event) {
      ag_ui.RunStartedEvent() => 'RunStarted',
      ag_ui.RunFinishedEvent() => 'RunFinished',
      ag_ui.RunErrorEvent(message: final msg) => 'RunError($msg)',
      ag_ui.TextMessageStartEvent(messageId: final id) => 'TextMessageStart($id)',
      ag_ui.TextMessageContentEvent(delta: final d) => 'TextMessageContent("${d.length > 50 ? '${d.substring(0, 50)}...' : d}")',
      ag_ui.TextMessageEndEvent(messageId: final id) => 'TextMessageEnd($id)',
      ag_ui.ThinkingTextMessageStartEvent() => 'ThinkingStart',
      ag_ui.ThinkingTextMessageContentEvent(delta: final d) => 'ThinkingContent("${d.length > 30 ? '${d.substring(0, 30)}...' : d}")',
      ag_ui.ThinkingTextMessageEndEvent() => 'ThinkingEnd',
      ag_ui.ToolCallStartEvent(toolCallId: final id) => 'ToolCallStart($id)',
      ag_ui.ToolCallEndEvent(toolCallId: final id) => 'ToolCallEnd($id)',
      ag_ui.StateSnapshotEvent() => 'StateSnapshot',
      ag_ui.StateDeltaEvent() => 'StateDelta',
      _ => event.runtimeType.toString(),
    };
  }

  Future<void> _setThreadMeta() async {
    final roomId = _roomIdController.text.trim();
    final threadId = _threadIdController.text.trim();
    if (roomId.isEmpty || threadId.isEmpty) {
      _log('Error: Room ID and Thread ID are required', isError: true);
      return;
    }

    _log('POST /api/v1/rooms/$roomId/agui/$threadId/meta');
    try {
      final client = ref.read(soliplexClientProvider);
      await client.setThreadMeta(roomId, threadId, name: 'Test Thread');
      _log('Response: Metadata updated');
    } catch (e) {
      _log('Error: $e', isError: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Test Page'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_sweep),
            tooltip: 'Clear logs',
            onPressed: _clearLogs,
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Server URL section
            _buildServerSection(),
            const SizedBox(height: 16),

            // ID inputs
            _buildIdInputs(),
            const SizedBox(height: 16),

            // Endpoint buttons
            _buildEndpointButtons(),
            const SizedBox(height: 16),

            // Message input for chat
            _buildMessageInput(),
            const SizedBox(height: 16),

            // Logs section
            Expanded(child: _buildLogsSection()),
          ],
        ),
      ),
    );
  }

  Widget _buildServerSection() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _serverUrlController,
                decoration: const InputDecoration(
                  labelText: 'Server URL',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
            ),
            const SizedBox(width: 12),
            ElevatedButton.icon(
              onPressed: _connect,
              icon: Icon(_isConnected ? Icons.check_circle : Icons.link),
              label: Text(_isConnected ? 'Connected' : 'Connect'),
              style: ElevatedButton.styleFrom(
                backgroundColor: _isConnected ? Colors.green : null,
                foregroundColor: _isConnected ? Colors.white : null,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildIdInputs() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _roomIdController,
                decoration: const InputDecoration(
                  labelText: 'Room ID',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: TextField(
                controller: _threadIdController,
                decoration: const InputDecoration(
                  labelText: 'Thread ID',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: TextField(
                controller: _runIdController,
                decoration: const InputDecoration(
                  labelText: 'Run ID',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEndpointButtons() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            _endpointButton('Get Rooms', Icons.meeting_room, _getRooms),
            _endpointButton('Get Threads', Icons.forum, _getThreads),
            _endpointButton('Create Thread', Icons.add_comment, _createThread),
            _endpointButton('Delete Thread', Icons.delete, _deleteThread),
            _endpointButton('Create Run', Icons.play_arrow, _createRun),
            _endpointButton('Set Meta', Icons.edit, _setThreadMeta),
          ],
        ),
      ),
    );
  }

  Widget _endpointButton(String label, IconData icon, VoidCallback onPressed) {
    return ElevatedButton.icon(
      onPressed: _isConnected ? onPressed : null,
      icon: Icon(icon, size: 18),
      label: Text(label),
    );
  }

  Widget _buildMessageInput() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _messageController,
                decoration: const InputDecoration(
                  labelText: 'Message',
                  hintText: 'Enter chat message...',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
                onSubmitted: (_) => _chat(),
              ),
            ),
            const SizedBox(width: 12),
            ElevatedButton.icon(
              onPressed: _isConnected ? _chat : null,
              icon: const Icon(Icons.send),
              label: const Text('Send'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Theme.of(context).colorScheme.primary,
                foregroundColor: Theme.of(context).colorScheme.onPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLogsSection() {
    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            child: Row(
              children: [
                const Icon(Icons.terminal, size: 18),
                const SizedBox(width: 8),
                const Text(
                  'Logs',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                const Spacer(),
                Text(
                  '${_logs.length} entries',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          Expanded(
            child: ListView.builder(
              controller: _logController,
              padding: const EdgeInsets.all(8),
              itemCount: _logs.length,
              itemBuilder: (context, index) {
                final log = _logs[index];
                return _LogEntryWidget(entry: log);
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _LogEntry {
  const _LogEntry({
    required this.timestamp,
    required this.message,
    this.isError = false,
    this.isEvent = false,
  });

  final DateTime timestamp;
  final String message;
  final bool isError;
  final bool isEvent;
}

class _LogEntryWidget extends StatelessWidget {
  const _LogEntryWidget({required this.entry});

  final _LogEntry entry;

  @override
  Widget build(BuildContext context) {
    final timeStr =
        '${entry.timestamp.hour.toString().padLeft(2, '0')}:'
        '${entry.timestamp.minute.toString().padLeft(2, '0')}:'
        '${entry.timestamp.second.toString().padLeft(2, '0')}';

    Color textColor;
    if (entry.isError) {
      textColor = Colors.red;
    } else if (entry.isEvent) {
      textColor = Colors.blue;
    } else {
      textColor = Theme.of(context).textTheme.bodyMedium?.color ?? Colors.black;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '[$timeStr] ',
            style: const TextStyle(
              fontFamily: 'monospace',
              fontSize: 12,
              color: Colors.grey,
            ),
          ),
          Expanded(
            child: SelectableText(
              entry.message,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                color: textColor,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
