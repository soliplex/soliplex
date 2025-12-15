import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:soliplex/core/config/feature_flags.dart';
import 'package:soliplex/core/providers/app_providers.dart';

class ServerSelector extends ConsumerWidget {
  const ServerSelector({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentServer = ref.watch(currentServerFromAppStateProvider);
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
                    context.go('/setup');
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
