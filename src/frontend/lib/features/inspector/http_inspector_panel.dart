import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_frontend/core/providers/http_log_provider.dart';
import 'package:soliplex_frontend/features/inspector/models/http_event_grouper.dart';
import 'package:soliplex_frontend/features/inspector/widgets/http_event_tile.dart';

/// Panel displaying HTTP traffic log for debugging.
class HttpInspectorPanel extends ConsumerWidget {
  const HttpInspectorPanel({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final events = ref.watch(httpLogProvider);
    final groups = groupHttpEvents(events);
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _buildHeader(theme, ref, groups.length),
        const Divider(height: 1),
        Expanded(
          child: groups.isEmpty
              ? Center(
                  child: Text(
                    'No HTTP activity yet',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                )
              : ListView.separated(
                  // Scroll to bottom (newest) by default
                  reverse: true,
                  itemCount: groups.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  // Reverse index so newest appears at bottom
                  itemBuilder: (context, index) {
                    final reversedIndex = groups.length - 1 - index;
                    return HttpEventTile(group: groups[reversedIndex]);
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildHeader(ThemeData theme, WidgetRef ref, int requestCount) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          Text(
            'HTTP Inspector',
            style: theme.textTheme.titleMedium,
          ),
          const Spacer(),
          if (requestCount > 0)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: Text(
                '$requestCount ${requestCount == 1 ? 'request' : 'requests'}',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          IconButton(
            icon: const Icon(Icons.delete_outline),
            onPressed: () => ref.read(httpLogProvider.notifier).clear(),
            tooltip: 'Clear log',
          ),
        ],
      ),
    );
  }
}
