import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/providers/app_providers.dart';
import 'package:soliplex/features/server/server_history_widget.dart';

/// Header widget showing current server with ability to switch.
///
/// Shows:
/// - Current server name/URL
/// - Connection status indicator
/// - Dropdown to switch servers
/// - User info when authenticated
class ServerSelector extends ConsumerWidget {
  const ServerSelector({super.key, this.onAddServer, this.onSettingsTap});
  final VoidCallback? onAddServer;
  final VoidCallback? onSettingsTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentServer = ref.watch(currentServerFromAppStateProvider);
    final appStateAsync = ref.watch(appStateStreamProvider);
    final appState = appStateAsync.valueOrNull;
    final theme = Theme.of(context);

    if (currentServer == null) {
      return TextButton.icon(
        onPressed: onAddServer,
        icon: const Icon(Icons.add),
        label: const Text('Add Server'),
      );
    }

    final userName = appState is AppStateReady ? appState.userName : null;

    return InkWell(
      onTap: () => _showServerMenu(context, ref),
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Server icon with status
            Stack(
              children: [
                Icon(
                  Icons.dns_outlined,
                  size: 20,
                  color: theme.colorScheme.onSurface,
                ),
                Positioned(
                  right: -2,
                  bottom: -2,
                  child: Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: _getStatusColor(appState, theme),
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: theme.colorScheme.surface,
                        width: 1.5,
                      ),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(width: 8),

            // Server name
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  currentServer.label,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w500,
                  ),
                ),
                if (userName != null)
                  Text(
                    userName,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
              ],
            ),

            const SizedBox(width: 4),
            Icon(
              Icons.arrow_drop_down,
              size: 20,
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ],
        ),
      ),
    );
  }

  Color _getStatusColor(AppState? state, ThemeData theme) {
    return switch (state) {
      AppStateReady() => Colors.green,
      AppStateAuthenticating() => Colors.orange,
      AppStateNeedsAuth() => Colors.orange,
      AppStateError() => theme.colorScheme.error,
      AppStateNoServer() => Colors.grey,
      null => Colors.grey,
    };
  }

  void _showServerMenu(BuildContext context, WidgetRef ref) {
    final button = context.findRenderObject()! as RenderBox;
    final overlay =
        Overlay.of(context).context.findRenderObject()! as RenderBox;
    final offset = button.localToGlobal(
      Offset(0, button.size.height),
      ancestor: overlay,
    );

    showMenu(
      context: context,
      position: RelativeRect.fromLTRB(
        offset.dx,
        offset.dy,
        overlay.size.width - offset.dx - button.size.width,
        overlay.size.height - offset.dy,
      ),
      items: [
        PopupMenuItem(
          enabled: false,
          child: ServerHistoryPopup(
            onAddNew: () {
              Navigator.pop(context);
              onAddServer?.call();
            },
          ),
        ),
      ],
    );
  }
}

/// Compact chip showing current server
class ServerChip extends ConsumerWidget {
  const ServerChip({super.key, this.onTap});
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentServer = ref.watch(currentServerFromAppStateProvider);
    final appStateAsync = ref.watch(appStateStreamProvider);
    final appState = appStateAsync.valueOrNull;

    if (currentServer == null) {
      return const SizedBox.shrink();
    }

    return ActionChip(
      avatar: Icon(
        Icons.dns_outlined,
        size: 16,
        color: _getStatusColor(appState),
      ),
      label: Text(currentServer.label),
      onPressed: onTap,
    );
  }

  Color _getStatusColor(AppState? state) {
    return switch (state) {
      AppStateReady() => Colors.green,
      AppStateAuthenticating() => Colors.orange,
      AppStateNeedsAuth() => Colors.orange,
      AppStateError() => Colors.red,
      AppStateNoServer() => Colors.grey,
      null => Colors.grey,
    };
  }
}

/// User avatar/menu when authenticated
class UserMenu extends ConsumerWidget {
  const UserMenu({super.key, this.onLogout, this.onSettingsTap});
  final VoidCallback? onLogout;
  final VoidCallback? onSettingsTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final appStateAsync = ref.watch(appStateStreamProvider);
    final appState = appStateAsync.valueOrNull;
    final theme = Theme.of(context);

    if (appState is! AppStateReady) {
      return const SizedBox.shrink();
    }

    final userName = appState.userName;
    final userEmail = appState.userEmail;
    final initial = (userName ?? userEmail ?? '?')
        .substring(0, 1)
        .toUpperCase();

    return PopupMenuButton<String>(
      offset: const Offset(0, 40),
      child: CircleAvatar(
        radius: 16,
        backgroundColor: theme.colorScheme.primaryContainer,
        child: Text(
          initial,
          style: TextStyle(
            color: theme.colorScheme.onPrimaryContainer,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      itemBuilder: (context) => [
        PopupMenuItem(
          enabled: false,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (userName != null)
                Text(userName, style: theme.textTheme.titleSmall),
              if (userEmail != null)
                Text(userEmail, style: theme.textTheme.bodySmall),
            ],
          ),
        ),
        const PopupMenuDivider(),
        if (onSettingsTap != null)
          const PopupMenuItem(
            value: 'settings',
            child: Row(
              children: [
                Icon(Icons.settings, size: 20),
                SizedBox(width: 8),
                Text('Settings'),
              ],
            ),
          ),
        PopupMenuItem(
          value: 'logout',
          child: Row(
            children: [
              Icon(Icons.logout, size: 20, color: theme.colorScheme.error),
              const SizedBox(width: 8),
              Text('Logout', style: TextStyle(color: theme.colorScheme.error)),
            ],
          ),
        ),
      ],
      onSelected: (value) {
        switch (value) {
          case 'settings':
            onSettingsTap?.call();
          case 'logout':
            _confirmLogout(context, ref);
        }
      },
    );
  }

  Future<void> _confirmLogout(BuildContext context, WidgetRef ref) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Logout?'),
        content: const Text('Are you sure you want to logout?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Logout'),
          ),
        ],
      ),
    );

    if (confirmed ?? false) {
      await ref.read(appStateManagerProvider).logout();
      onLogout?.call();
    }
  }
}
