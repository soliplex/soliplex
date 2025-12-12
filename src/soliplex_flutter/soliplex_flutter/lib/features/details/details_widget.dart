import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../client/client.dart';
import '../../providers/providers.dart';

/// Widget displaying detailed information about the current thread.
///
/// Shows run list, thinking content, state history, and tool call details.
class DetailsWidget extends ConsumerWidget {
  const DetailsWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final roomId = ref.watch(currentRoomProvider);
    final threadId = ref.watch(currentThreadProvider);

    if (roomId == null) {
      return const _EmptyDetails(message: 'Select a room');
    }

    if (threadId == null) {
      return const _EmptyDetails(message: 'Select a thread');
    }

    final messagesAsync = ref.watch(roomMessagesProvider(roomId));
    final canvasState = ref.watch(canvasStateProvider);

    return DefaultTabController(
      length: 3,
      child: Column(
        children: [
          _DetailsHeader(threadId: threadId),
          const TabBar(
            tabs: [
              Tab(text: 'Messages'),
              Tab(text: 'Thinking'),
              Tab(text: 'State'),
            ],
          ),
          Expanded(
            child: TabBarView(
              children: [
                messagesAsync.when(
                  data: (messages) => _MessagesTab(messages: messages),
                  loading: () => const Center(child: CircularProgressIndicator()),
                  error: (error, _) => _ErrorContent(error: error.toString()),
                ),
                messagesAsync.when(
                  data: (messages) => _ThinkingTab(messages: messages),
                  loading: () => const Center(child: CircularProgressIndicator()),
                  error: (error, _) => _ErrorContent(error: error.toString()),
                ),
                _StateTab(state: canvasState),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _DetailsHeader extends StatelessWidget {
  const _DetailsHeader({required this.threadId});

  final String threadId;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).dividerColor,
          ),
        ),
      ),
      child: Row(
        children: [
          const Icon(Icons.info_outline, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Details',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                  ),
                ),
                Text(
                  'Thread: ${threadId.substring(0, 8)}...',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.outline,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MessagesTab extends StatelessWidget {
  const _MessagesTab({required this.messages});

  final List<ChatMessage> messages;

  @override
  Widget build(BuildContext context) {
    if (messages.isEmpty) {
      return const _EmptyContent(message: 'No messages yet');
    }

    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: messages.length,
      itemBuilder: (context, index) {
        final message = messages[index];
        return _MessageDetailCard(message: message);
      },
    );
  }
}

class _MessageDetailCard extends StatelessWidget {
  const _MessageDetailCard({required this.message});

  final ChatMessage message;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final (icon, color, typeLabel) = switch (message.type) {
      MessageType.text => (Icons.chat, theme.colorScheme.primary, 'Text'),
      MessageType.error => (Icons.error, Colors.red, 'Error'),
      MessageType.toolCall => (Icons.build, theme.colorScheme.secondary, 'Tool'),
      MessageType.genUi => (Icons.widgets, theme.colorScheme.tertiary, 'GenUI'),
      MessageType.loading => (Icons.hourglass_empty, Colors.grey, 'Loading'),
    };

    final userLabel = switch (message.user) {
      ChatUser.user => 'User',
      ChatUser.assistant => 'Assistant',
      ChatUser.system => 'System',
    };

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ExpansionTile(
        leading: CircleAvatar(
          radius: 14,
          backgroundColor: color.withValues(alpha: 0.2),
          child: Icon(icon, size: 14, color: color),
        ),
        title: Row(
          children: [
            Text(
              userLabel,
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                typeLabel,
                style: TextStyle(fontSize: 10, color: color),
              ),
            ),
          ],
        ),
        subtitle: Text(
          _formatTime(message.createdAt),
          style: theme.textTheme.bodySmall,
        ),
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _DetailRow(label: 'ID', value: message.id),
                if (message.text?.isNotEmpty ?? false)
                  _DetailRow(
                    label: 'Content',
                    value: message.text!,
                    multiline: true,
                  ),
                if (message.errorMessage?.isNotEmpty ?? false)
                  _DetailRow(
                    label: 'Error',
                    value: message.errorMessage!,
                    multiline: true,
                  ),
                if (message.toolCalls?.isNotEmpty ?? false)
                  _DetailRow(
                    label: 'Tool Calls',
                    value: message.toolCalls!.map((t) => '${t.name} (${t.status.name})').join(', '),
                  ),
                if (message.isStreaming)
                  const _DetailRow(label: 'Status', value: 'Streaming...'),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _formatTime(DateTime time) {
    return '${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}:${time.second.toString().padLeft(2, '0')}';
  }
}

class _ThinkingTab extends StatelessWidget {
  const _ThinkingTab({required this.messages});

  final List<ChatMessage> messages;

  @override
  Widget build(BuildContext context) {
    final thinkingMessages = messages
        .where((m) => m.thinkingText?.isNotEmpty ?? false)
        .toList();

    if (thinkingMessages.isEmpty) {
      return const _EmptyContent(message: 'No thinking content');
    }

    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: thinkingMessages.length,
      itemBuilder: (context, index) {
        final message = thinkingMessages[index];
        return _ThinkingCard(message: message);
      },
    );
  }
}

class _ThinkingCard extends StatelessWidget {
  const _ThinkingCard({required this.message});

  final ChatMessage message;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.psychology,
                  size: 16,
                  color: theme.colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Text(
                  'Thinking',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: theme.colorScheme.primary,
                  ),
                ),
                const Spacer(),
                if (message.isThinkingStreaming)
                  SizedBox(
                    width: 12,
                    height: 12,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: theme.colorScheme.primary,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(8),
              ),
              child: SelectableText(
                message.thinkingText ?? '',
                style: TextStyle(
                  fontStyle: FontStyle.italic,
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StateTab extends StatelessWidget {
  const _StateTab({required this.state});

  final Map<String, dynamic> state;

  @override
  Widget build(BuildContext context) {
    if (state.isEmpty) {
      return const _EmptyContent(message: 'No state data');
    }

    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: state.length,
      itemBuilder: (context, index) {
        final key = state.keys.elementAt(index);
        final value = state[key];
        return _StateCard(stateKey: key, value: value);
      },
    );
  }
}

class _StateCard extends StatelessWidget {
  const _StateCard({
    required this.stateKey,
    required this.value,
  });

  final String stateKey;
  final dynamic value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ExpansionTile(
        leading: Icon(
          _getIcon(value),
          color: theme.colorScheme.secondary,
        ),
        title: Text(stateKey),
        subtitle: Text(_getTypeLabel(value)),
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(8),
              ),
              child: SelectableText(
                _formatValue(value),
                style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
              ),
            ),
          ),
        ],
      ),
    );
  }

  IconData _getIcon(dynamic value) {
    if (value is Map) return Icons.data_object;
    if (value is List) return Icons.data_array;
    if (value is num) return Icons.numbers;
    if (value is bool) return Icons.toggle_on;
    return Icons.text_fields;
  }

  String _getTypeLabel(dynamic value) {
    if (value is Map) return 'Object (${value.length} keys)';
    if (value is List) return 'Array (${value.length} items)';
    if (value is int) return 'Integer';
    if (value is double) return 'Double';
    if (value is bool) return 'Boolean';
    if (value is String) return 'String (${value.length} chars)';
    return value.runtimeType.toString();
  }

  String _formatValue(dynamic value) {
    if (value is Map || value is List) {
      try {
        const encoder = JsonEncoder.withIndent('  ');
        return encoder.convert(value);
      } catch (_) {
        return value.toString();
      }
    }
    return value.toString();
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({
    required this.label,
    required this.value,
    this.multiline = false,
  });

  final String label;
  final String value;
  final bool multiline;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: multiline
          ? Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 12,
                    color: theme.colorScheme.outline,
                  ),
                ),
                const SizedBox(height: 4),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: SelectableText(
                    value,
                    style: const TextStyle(fontSize: 12),
                  ),
                ),
              ],
            )
          : Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 80,
                  child: Text(
                    label,
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                      color: theme.colorScheme.outline,
                    ),
                  ),
                ),
                Expanded(
                  child: SelectableText(
                    value,
                    style: const TextStyle(fontSize: 12),
                  ),
                ),
              ],
            ),
    );
  }
}

class _EmptyDetails extends StatelessWidget {
  const _EmptyDetails({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.info_outline,
            size: 64,
            color: theme.colorScheme.outline,
          ),
          const SizedBox(height: 16),
          Text(
            message,
            style: TextStyle(
              fontSize: 16,
              color: theme.colorScheme.outline,
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyContent extends StatelessWidget {
  const _EmptyContent({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Center(
      child: Text(
        message,
        style: TextStyle(color: theme.colorScheme.outline),
      ),
    );
  }
}

class _ErrorContent extends StatelessWidget {
  const _ErrorContent({required this.error});

  final String error;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Text(
        'Error: $error',
        style: const TextStyle(color: Colors.red),
      ),
    );
  }
}

class JsonEncoder {
  const JsonEncoder.withIndent(this._indent);

  final String _indent;

  String convert(dynamic value) => _encode(value, 0);

  String _encode(dynamic value, int depth) {
    final prefix = _indent * depth;
    final nextPrefix = _indent * (depth + 1);

    if (value is Map) {
      if (value.isEmpty) return '{}';
      final entries = value.entries.map((e) {
        final key = '"${e.key}"';
        final val = _encode(e.value, depth + 1);
        return '$nextPrefix$key: $val';
      }).join(',\n');
      return '{\n$entries\n$prefix}';
    }

    if (value is List) {
      if (value.isEmpty) return '[]';
      final items = value.map((e) => '$nextPrefix${_encode(e, depth + 1)}').join(',\n');
      return '[\n$items\n$prefix]';
    }

    if (value is String) return '"$value"';
    if (value == null) return 'null';
    return value.toString();
  }
}
