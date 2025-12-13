import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../providers/providers.dart';

/// Widget displaying the current canvas state from AG-UI events.
///
/// Scoped to the current thread, updates when StateSnapshot or StateDelta arrives.
class CurrentCanvasWidget extends ConsumerWidget {
  const CurrentCanvasWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final canvasState = ref.watch(canvasStateProvider);
    final isActive = ref.watch(isAgentActiveProvider);

    if (canvasState.isEmpty) {
      return _EmptyCanvas(isActive: isActive);
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _CanvasHeader(
          onClear: () => ref.read(canvasStateProvider.notifier).clear(),
        ),
        Expanded(
          child: _CanvasContent(state: canvasState),
        ),
      ],
    );
  }
}

class _CanvasHeader extends StatelessWidget {
  const _CanvasHeader({required this.onClear});

  final VoidCallback onClear;

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
          const Icon(Icons.dashboard, size: 20),
          const SizedBox(width: 8),
          const Expanded(
            child: Text(
              'Canvas',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 16,
              ),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.clear_all),
            tooltip: 'Clear Canvas',
            onPressed: onClear,
            iconSize: 20,
            constraints: const BoxConstraints(
              minWidth: 32,
              minHeight: 32,
            ),
          ),
        ],
      ),
    );
  }
}

class _CanvasContent extends StatelessWidget {
  const _CanvasContent({required this.state});

  final Map<String, dynamic> state;

  @override
  Widget build(BuildContext context) {
    final entries = state.entries.toList();

    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: entries.length,
      itemBuilder: (context, index) {
        final entry = entries[index];
        return _StateCard(
          key: ValueKey(entry.key),
          stateKey: entry.key,
          value: entry.value,
        );
      },
    );
  }
}

class _StateCard extends StatelessWidget {
  const _StateCard({
    required this.stateKey,
    required this.value,
    super.key,
  });

  final String stateKey;
  final dynamic value;

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
                  _getIconForValue(value),
                  size: 16,
                  color: theme.colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    stateKey,
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.secondaryContainer,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    _getTypeLabel(value),
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: theme.colorScheme.onSecondaryContainer,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            _ValueDisplay(value: value),
          ],
        ),
      ),
    );
  }

  IconData _getIconForValue(dynamic value) {
    if (value is Map) return Icons.data_object;
    if (value is List) return Icons.data_array;
    if (value is num) return Icons.numbers;
    if (value is bool) return Icons.toggle_on;
    if (value is String) return Icons.text_fields;
    return Icons.help_outline;
  }

  String _getTypeLabel(dynamic value) {
    if (value is Map) return 'object';
    if (value is List) return 'array[${value.length}]';
    if (value is int) return 'int';
    if (value is double) return 'double';
    if (value is bool) return 'bool';
    if (value is String) return 'string';
    return value.runtimeType.toString();
  }
}

class _ValueDisplay extends StatelessWidget {
  const _ValueDisplay({required this.value});

  final dynamic value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    if (value is Map) {
      return _MapDisplay(map: value as Map<String, dynamic>);
    }

    if (value is List) {
      return _ListDisplay(list: value as List<dynamic>);
    }

    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(4),
      ),
      child: SelectableText(
        value.toString(),
        style: const TextStyle(fontFamily: 'monospace'),
      ),
    );
  }
}

class _MapDisplay extends StatelessWidget {
  const _MapDisplay({required this.map});

  final Map<String, dynamic> map;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: map.entries.take(5).map((entry) {
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 2),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${entry.key}: ',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    color: theme.colorScheme.primary,
                  ),
                ),
                Expanded(
                  child: SelectableText(
                    _formatValue(entry.value),
                    style: const TextStyle(fontFamily: 'monospace'),
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  String _formatValue(dynamic value) {
    if (value is String && value.length > 50) {
      return '"${value.substring(0, 50)}..."';
    }
    if (value is String) return '"$value"';
    if (value is Map) return '{...}';
    if (value is List) return '[${value.length} items]';
    return value.toString();
  }
}

class _ListDisplay extends StatelessWidget {
  const _ListDisplay({required this.list});

  final List<dynamic> list;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (var i = 0; i < list.length && i < 5; i++)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 2),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '[$i] ',
                    style: TextStyle(
                      fontFamily: 'monospace',
                      color: theme.colorScheme.outline,
                    ),
                  ),
                  Expanded(
                    child: SelectableText(
                      _formatValue(list[i]),
                      style: const TextStyle(fontFamily: 'monospace'),
                    ),
                  ),
                ],
              ),
            ),
          if (list.length > 5)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                '... and ${list.length - 5} more items',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.outline,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ),
        ],
      ),
    );
  }

  String _formatValue(dynamic value) {
    if (value is String && value.length > 30) {
      return '"${value.substring(0, 30)}..."';
    }
    if (value is String) return '"$value"';
    if (value is Map) return '{...}';
    if (value is List) return '[${value.length}]';
    return value.toString();
  }
}

class _EmptyCanvas extends StatelessWidget {
  const _EmptyCanvas({required this.isActive});

  final bool isActive;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            isActive ? Icons.hourglass_top : Icons.dashboard_outlined,
            size: 64,
            color: theme.colorScheme.outline,
          ),
          const SizedBox(height: 16),
          Text(
            isActive ? 'Waiting for canvas data...' : 'No canvas data yet',
            style: TextStyle(
              fontSize: 16,
              color: theme.colorScheme.outline,
            ),
          ),
          if (isActive)
            Padding(
              padding: const EdgeInsets.only(top: 16),
              child: SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: theme.colorScheme.outline,
                ),
              ),
            ),
        ],
      ),
    );
  }
}
