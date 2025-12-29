import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/models/server_models.dart';
import 'package:soliplex/core/providers/app_providers.dart';

/// Widget displaying saved server connections.
///
/// Shows a list of previously connected servers with:
/// - Server URL/name
/// - Last connected time
/// - Auth status indicator
/// - Delete option
class ServerHistoryWidget extends ConsumerWidget {
  const ServerHistoryWidget({
    super.key,
    this.onServerSelected,
    this.showDeleteButton = true,
  });
  final void Function(ServerConnection server)? onServerSelected;
  final bool showDeleteButton;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final history = ref.watch(serverHistoryProvider);
    final currentServer = ref.watch(currentServerFromAppStateProvider);

    if (history.isEmpty) {
      return const Center(child: Text('No saved servers'));
    }

    return ListView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: history.length,
      itemBuilder: (context, index) {
        final server = history[index];
        final isSelected = server.id == currentServer?.id;

        return _ServerHistoryTile(
          server: server,
          isSelected: isSelected,
          showDeleteButton: showDeleteButton,
          onTap: () => onServerSelected?.call(server),
          onDelete: () => _confirmDelete(context, ref, server),
        );
      },
    );
  }

  Future<void> _confirmDelete(
    BuildContext context,
    WidgetRef ref,
    ServerConnection server,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Remove Server?'),
        content: Text(
          'Remove "${server.label}" from your saved servers?\n\n'
          'This will also clear any stored credentials.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );

    if (confirmed ?? false) {
      await ref
          .read(appStateManagerProvider)
          .removeServerFromHistory(server.id);
    }
  }
}

class _ServerHistoryTile extends StatelessWidget {
  const _ServerHistoryTile({
    required this.server,
    required this.isSelected,
    required this.showDeleteButton,
    this.onTap,
    this.onDelete,
  });
  final ServerConnection server;
  final bool isSelected;
  final bool showDeleteButton;
  final VoidCallback? onTap;
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return ListTile(
      leading: CircleAvatar(
        backgroundColor: isSelected
            ? theme.colorScheme.primaryContainer
            : theme.colorScheme.surfaceContainerHighest,
        child: Icon(
          isSelected ? Icons.check : Icons.dns_outlined,
          color: isSelected
              ? theme.colorScheme.onPrimaryContainer
              : theme.colorScheme.onSurfaceVariant,
        ),
      ),
      title: Text(
        server.label,
        style: TextStyle(
          fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
        ),
      ),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (server.displayName != null)
            Text(server.url, style: theme.textTheme.bodySmall),
          Row(
            children: [
              Icon(
                server.requiresAuth ? Icons.lock : Icons.lock_open,
                size: 12,
                color: theme.colorScheme.onSurfaceVariant,
              ),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  server.requiresAuth ? 'Authenticated' : 'Open',
                  style: theme.textTheme.bodySmall,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  _formatLastConnected(server.lastConnected),
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                  textAlign: TextAlign.end,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ],
      ),
      trailing: showDeleteButton
          ? IconButton(
              icon: const Icon(Icons.close),
              onPressed: onDelete,
              tooltip: 'Remove',
            )
          : null,
      selected: isSelected,
      onTap: onTap,
    );
  }

  String _formatLastConnected(DateTime lastConnected) {
    final now = DateTime.now();
    final diff = now.difference(lastConnected);

    if (diff.inMinutes < 1) {
      return 'Just now';
    } else if (diff.inHours < 1) {
      return '${diff.inMinutes}m ago';
    } else if (diff.inDays < 1) {
      return '${diff.inHours}h ago';
    } else if (diff.inDays < 7) {
      return '${diff.inDays}d ago';
    } else {
      return '${lastConnected.month}/${lastConnected.day}';
    }
  }
}

/// Compact server history for dropdown/popup menus
class ServerHistoryPopup extends ConsumerWidget {
  const ServerHistoryPopup({super.key, this.onAddNew});
  final VoidCallback? onAddNew;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final history = ref.watch(serverHistoryProvider);
    final currentServer = ref.watch(currentServerFromAppStateProvider);
    final theme = Theme.of(context);

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Text('Servers', style: theme.textTheme.titleSmall),
        ),
        const Divider(height: 1),
        ...history.map((server) {
          final isSelected = server.id == currentServer?.id;
          return ListTile(
            dense: true,
            leading: Icon(
              isSelected ? Icons.check_circle : Icons.dns_outlined,
              size: 20,
              color: isSelected ? theme.colorScheme.primary : null,
            ),
            title: Text(server.label),
            subtitle: Text(
              server.requiresAuth ? 'Authenticated' : 'Open',
              style: theme.textTheme.bodySmall,
            ),
            selected: isSelected,
            onTap: () {
              ref
                  .read(appStateManagerProvider)
                  .selectServerFromHistory(server.id);
              Navigator.pop(context);
            },
          );
        }),
        const Divider(height: 1),
        ListTile(
          dense: true,
          leading: const Icon(Icons.add),
          title: const Text('Add Server'),
          onTap: () {
            Navigator.pop(context);
            onAddNew?.call();
          },
        ),
      ],
    );
  }
}
