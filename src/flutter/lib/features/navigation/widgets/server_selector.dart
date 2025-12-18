import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:soliplex/core/config/feature_flags.dart';
import 'package:soliplex/core/providers/app_providers.dart';
import 'package:soliplex/core/utils/debug_log.dart';

class ServerSelector extends ConsumerWidget {
  const ServerSelector({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentServer = ref.watch(currentServerFromAppStateProvider);
    DebugLog.service(
      'ServerSelector: currentServer=${currentServer?.label}, '
      'requiresAuth=${currentServer?.requiresAuth}',
    );
    final enableEndpointManagement = ref.watch(
      enableEndpointManagementProvider,
    );

    return UserAccountsDrawerHeader(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.primaryContainer,
      ),
      accountName: Text(
        currentServer?.label ?? 'No Server',
        style: TextStyle(
          color: Theme.of(context).colorScheme.onPrimaryContainer,
        ),
      ),
      accountEmail: Text(
        currentServer?.url ?? '',
        style: TextStyle(
          color: Theme.of(context).colorScheme.onPrimaryContainer,
        ),
      ),
      currentAccountPicture: CircleAvatar(
        backgroundColor: Theme.of(context).colorScheme.primary,
        foregroundColor: Theme.of(context).colorScheme.onPrimary,
        child: const Icon(Icons.dns),
      ),
      onDetailsPressed: () {
        showModalBottomSheet<void>(
          context: context,
          builder: (context) {
            return Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (enableEndpointManagement)
                  ListTile(
                    leading: const Icon(Icons.settings),
                    title: const Text('Manage Endpoints'),
                    onTap: () {
                      Navigator.pop(context);
                      context.push('/settings');
                    },
                  ),
                ListTile(
                  leading: const Icon(Icons.swap_horiz),
                  title: const Text('Switch Server'),
                  onTap: () {
                    Navigator.pop(context);
                    context.push('/setup');
                  },
                ),
                if (currentServer?.requiresAuth ?? false)
                  ListTile(
                    leading: const Icon(Icons.logout),
                    title: const Text('Logout'),
                    textColor: Theme.of(context).colorScheme.error,
                    iconColor: Theme.of(context).colorScheme.error,
                    onTap: () async {
                      Navigator.pop(context);
                      final confirmed = await showDialog<bool>(
                        context: context,
                        builder: (context) => AlertDialog(
                          title: const Text('Logout?'),
                          content: const Text(
                            'Are you sure you want to logout from this server?',
                          ),
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
                      }
                    },
                  ),
              ],
            );
          },
        );
      },
    );
  }
}
