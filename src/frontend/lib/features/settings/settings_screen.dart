import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_frontend/core/providers/config_provider.dart';

/// Settings screen for app configuration.
///
/// AM1: Display-only (no editing).
/// AM7: Add backend URL editing, authentication settings.
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final config = ref.watch(configProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
      ),
      body: ListView(
        children: [
          ListTile(
            leading: const Icon(Icons.info_outline),
            title: const Text('App Version'),
            subtitle: Text(config.version),
          ),
          ListTile(
            leading: const Icon(Icons.dns),
            title: const Text('Backend URL'),
            subtitle: Text(config.baseUrl),
            trailing: const Icon(Icons.edit_off),
            enabled: false,
            onTap: () {
              // TODO(AM7): Add URL editing
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Backend URL editing - Coming in AM7'),
                ),
              );
            },
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.login),
            title: const Text('Authentication'),
            subtitle: const Text('Not configured'),
            trailing: Chip(
              label: const Text('AM7'),
              backgroundColor:
                  Theme.of(context).colorScheme.secondaryContainer,
            ),
            enabled: false,
          ),
        ],
      ),
    );
  }
}
