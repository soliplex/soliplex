import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/network/network_inspector.dart';
import 'package:soliplex/core/network/network_inspector_models.dart';

/// Selected entry provider for detail view.
final selectedEntryIdProvider = StateProvider<String?>((ref) => null);

/// Network traffic inspector screen.
///
/// Displays HTTP requests/responses in a browser-dev-tools style interface.
class NetworkInspectorScreen extends ConsumerWidget {
  const NetworkInspectorScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final inspector = ref.watch(networkInspectorProvider);
    final entries = inspector.entries;
    final selectedId = ref.watch(selectedEntryIdProvider);
    final selectedEntry = selectedId != null
        ? inspector.getEntry(selectedId)
        : null;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Network Inspector'),
        actions: [
          // Entry count badge
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: Center(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '${entries.length} requests',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            ),
          ),
          // Clear button
          IconButton(
            icon: const Icon(Icons.delete_outline),
            tooltip: 'Clear all',
            onPressed: entries.isEmpty
                ? null
                : () {
                    ref.read(networkInspectorProvider).clear();
                    ref.read(selectedEntryIdProvider.notifier).state = null;
                  },
          ),
        ],
      ),
      body: entries.isEmpty
          ? const _EmptyState()
          : Column(
              children: [
                // Request list
                Expanded(
                  flex: selectedEntry != null ? 1 : 2,
                  child: _RequestList(
                    entries: entries,
                    selectedId: selectedId,
                    onSelect: (id) {
                      ref.read(selectedEntryIdProvider.notifier).state =
                          selectedId == id ? null : id;
                    },
                  ),
                ),
                // Detail view (when entry selected)
                if (selectedEntry != null) ...[
                  const Divider(height: 1),
                  Expanded(flex: 2, child: _DetailView(entry: selectedEntry)),
                ],
              ],
            ),
    );
  }
}

/// Empty state when no requests captured.
class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.wifi_tethering_off,
            size: 64,
            color: Theme.of(context).colorScheme.outline,
          ),
          const SizedBox(height: 16),
          Text(
            'No network traffic captured',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              color: Theme.of(context).colorScheme.outline,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Make some requests to see them here',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.outline,
            ),
          ),
        ],
      ),
    );
  }
}

/// List of captured requests.
class _RequestList extends StatelessWidget {
  const _RequestList({
    required this.entries,
    required this.selectedId,
    required this.onSelect,
  });
  final List<NetworkEntry> entries;
  final String? selectedId;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Header row
        _HeaderRow(),
        const Divider(height: 1),
        // Entries
        Expanded(
          child: ListView.builder(
            itemCount: entries.length,
            itemBuilder: (context, index) {
              final entry = entries[index];
              return _RequestRow(
                entry: entry,
                isSelected: entry.id == selectedId,
                onTap: () => onSelect(entry.id),
              );
            },
          ),
        ),
      ],
    );
  }
}

/// Header row for the request list.
class _HeaderRow extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final textStyle = Theme.of(context).textTheme.labelSmall?.copyWith(
      fontWeight: FontWeight.bold,
      color: Theme.of(context).colorScheme.onSurfaceVariant,
    );

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Row(
        children: [
          SizedBox(width: 60, child: Text('Method', style: textStyle)),
          SizedBox(width: 60, child: Text('Status', style: textStyle)),
          Expanded(child: Text('URL', style: textStyle)),
          SizedBox(
            width: 80,
            child: Text(
              'Latency',
              style: textStyle,
              textAlign: TextAlign.right,
            ),
          ),
          SizedBox(
            width: 80,
            child: Text('Time', style: textStyle, textAlign: TextAlign.right),
          ),
        ],
      ),
    );
  }
}

/// Single request row in the list.
class _RequestRow extends StatelessWidget {
  const _RequestRow({
    required this.entry,
    required this.isSelected,
    required this.onTap,
  });
  final NetworkEntry entry;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    // Status color
    Color statusColor;
    if (entry.isInFlight) {
      statusColor = theme.colorScheme.tertiary;
    } else if (entry.isSuccess) {
      statusColor = Colors.green;
    } else if (entry.isError) {
      statusColor = theme.colorScheme.error;
    } else {
      statusColor = theme.colorScheme.outline;
    }

    // Method color
    Color methodColor;
    switch (entry.method) {
      case 'GET':
        methodColor = Colors.blue;
      case 'POST':
        methodColor = Colors.green;
      case 'PUT':
        methodColor = Colors.orange;
      case 'DELETE':
        methodColor = Colors.red;
      default:
        methodColor = theme.colorScheme.onSurface;
    }

    return Material(
      color: isSelected
          ? theme.colorScheme.primaryContainer
          : Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            border: Border(
              bottom: BorderSide(
                color: theme.dividerColor.withValues(alpha: 0.3),
              ),
            ),
          ),
          child: Row(
            children: [
              // Method
              SizedBox(
                width: 60,
                child: Text(
                  entry.method,
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    color: methodColor,
                    fontFamily: 'monospace',
                  ),
                ),
              ),
              // Status
              SizedBox(
                width: 60,
                child: entry.isInFlight
                    ? SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: statusColor,
                        ),
                      )
                    : Text(
                        entry.statusCode?.toString() ??
                            (entry.error != null ? 'ERR' : '-'),
                        style: TextStyle(
                          color: statusColor,
                          fontWeight: FontWeight.w600,
                          fontFamily: 'monospace',
                        ),
                      ),
              ),
              // URL
              Expanded(
                child: Text(
                  entry.shortPath,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 12,
                    color: theme.colorScheme.onSurface,
                  ),
                ),
              ),
              // Latency
              SizedBox(
                width: 80,
                child: Text(
                  entry.latencyMs != null ? '${entry.latencyMs}ms' : '-',
                  textAlign: TextAlign.right,
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 12,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
              // Time
              SizedBox(
                width: 80,
                child: Text(
                  _formatTime(entry.startTime),
                  textAlign: TextAlign.right,
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 12,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatTime(DateTime time) {
    return '${time.hour.toString().padLeft(2, '0')}:'
        '${time.minute.toString().padLeft(2, '0')}:'
        '${time.second.toString().padLeft(2, '0')}';
  }
}

/// Detail view for a selected request.
class _DetailView extends StatelessWidget {
  const _DetailView({required this.entry});
  final NetworkEntry entry;

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 3,
      child: Column(
        children: [
          // Tab bar
          ColoredBox(
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            child: Row(
              children: [
                const Expanded(
                  child: TabBar(
                    tabs: [
                      Tab(text: 'Request'),
                      Tab(text: 'Response'),
                      Tab(text: 'curl'),
                    ],
                    isScrollable: true,
                    tabAlignment: TabAlignment.start,
                  ),
                ),
                // Close button
                IconButton(
                  icon: const Icon(Icons.close, size: 18),
                  tooltip: 'Close',
                  onPressed: () {
                    // Find the provider scope and clear selection
                    ProviderScope.containerOf(
                      context,
                    ).read(selectedEntryIdProvider.notifier).state = null;
                  },
                ),
              ],
            ),
          ),
          // Tab content
          Expanded(
            child: TabBarView(
              children: [
                _RequestTab(entry: entry),
                _ResponseTab(entry: entry),
                _CurlTab(entry: entry),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Request details tab.
class _RequestTab extends StatelessWidget {
  const _RequestTab({required this.entry});
  final NetworkEntry entry;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // URL
          _Section(
            title: 'URL',
            child: SelectableText(
              entry.fullUrl,
              style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
            ),
          ),
          const SizedBox(height: 16),
          // Headers
          _Section(
            title: 'Headers',
            child: _HeadersView(headers: entry.requestHeaders),
          ),
          // Body
          if (entry.requestBody != null) ...[
            const SizedBox(height: 16),
            _Section(
              title: 'Body',
              child: _BodyView(
                body: entry.formatRequestBody(),
                isJson: entry.isJsonRequest,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Response details tab.
class _ResponseTab extends StatelessWidget {
  const _ResponseTab({required this.entry});
  final NetworkEntry entry;

  @override
  Widget build(BuildContext context) {
    if (entry.isInFlight) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Waiting for response...'),
          ],
        ),
      );
    }

    if (entry.error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.error_outline,
              size: 48,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: 16),
            Text(
              'Request Failed',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            SelectableText(
              entry.error!,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                color: Theme.of(context).colorScheme.error,
              ),
            ),
          ],
        ),
      );
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Status
          _Section(
            title: 'Status',
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: entry.isSuccess
                        ? Colors.green.withValues(alpha: 0.2)
                        : Theme.of(
                            context,
                          ).colorScheme.error.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    '${entry.statusCode}',
                    style: TextStyle(
                      fontFamily: 'monospace',
                      fontWeight: FontWeight.bold,
                      color: entry.isSuccess
                          ? Colors.green
                          : Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                if (entry.latencyMs != null)
                  Text(
                    '${entry.latencyMs}ms',
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 12,
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          // Headers
          if (entry.responseHeaders != null)
            _Section(
              title: 'Headers',
              child: _HeadersView(headers: entry.responseHeaders!),
            ),
          // Body
          if (entry.responseBody != null) ...[
            const SizedBox(height: 16),
            _Section(
              title: 'Body',
              child: entry.isBinaryResponse
                  ? Text(
                      entry.formatResponseBody(),
                      style: TextStyle(
                        fontStyle: FontStyle.italic,
                        color: Theme.of(context).colorScheme.outline,
                      ),
                    )
                  : _BodyView(
                      body: entry.formatResponseBody(),
                      isJson: entry.isJsonResponse,
                    ),
            ),
          ],
        ],
      ),
    );
  }
}

/// curl command tab.
class _CurlTab extends StatelessWidget {
  const _CurlTab({required this.entry});
  final NetworkEntry entry;

  @override
  Widget build(BuildContext context) {
    final curl = entry.toCurl();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Copy button
        Padding(
          padding: const EdgeInsets.all(12),
          child: FilledButton.icon(
            onPressed: () {
              Clipboard.setData(ClipboardData(text: curl));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Copied to clipboard'),
                  duration: Duration(seconds: 2),
                ),
              );
            },
            icon: const Icon(Icons.copy, size: 18),
            label: const Text('Copy to clipboard'),
          ),
        ),
        // curl command
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
            child: SelectableText(
              curl,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                color: Theme.of(context).colorScheme.onSurface,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

/// Section with title.
class _Section extends StatelessWidget {
  const _Section({required this.title, required this.child});
  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(context).textTheme.labelMedium?.copyWith(
            fontWeight: FontWeight.bold,
            color: Theme.of(context).colorScheme.primary,
          ),
        ),
        const SizedBox(height: 8),
        child,
      ],
    );
  }
}

/// Headers view.
class _HeadersView extends StatelessWidget {
  const _HeadersView({required this.headers});
  final Map<String, String> headers;

  @override
  Widget build(BuildContext context) {
    if (headers.isEmpty) {
      return Text(
        'No headers',
        style: TextStyle(
          fontStyle: FontStyle.italic,
          color: Theme.of(context).colorScheme.outline,
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: headers.entries.map((e) {
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 2),
          child: SelectableText.rich(
            TextSpan(
              children: [
                TextSpan(
                  text: '${e.key}: ',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                ),
                TextSpan(
                  text: e.value,
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 12,
                    color: Theme.of(context).colorScheme.onSurface,
                  ),
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }
}

/// Body view with optional JSON highlighting.
class _BodyView extends StatelessWidget {
  const _BodyView({required this.body, required this.isJson});
  final String body;
  final bool isJson;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(4),
      ),
      child: SelectableText(
        body,
        style: TextStyle(
          fontFamily: 'monospace',
          fontSize: 12,
          color: Theme.of(context).colorScheme.onSurface,
        ),
      ),
    );
  }
}
