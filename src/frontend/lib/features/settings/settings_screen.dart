import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/auth_providers.dart';
import 'package:soliplex_frontend/core/providers/config_provider.dart';
import 'package:soliplex_frontend/core/state/app_state.dart';

/// Settings screen for app configuration.
///
/// Returns body content only; AppShell wrapper is provided by the router.
///
/// Shows:
/// - App version
/// - Server connection info (when connected)
/// - Current user info (when authenticated)
/// - Logout button (when authenticated)
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final config = ref.watch(configProvider);
    final appState = ref.watch(appStateProvider);

    return ListView(
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
        ),
        const Divider(),
        ..._buildAuthSection(context, ref, appState),
      ],
    );
  }

  List<Widget> _buildAuthSection(
    BuildContext context,
    WidgetRef ref,
    AppState appState,
  ) {
    switch (appState) {
      case AppStateReady(:final serverId, :final config, :final user):
        return [
          ListTile(
            leading: const Icon(Icons.cloud_done),
            title: const Text('Connected to'),
            subtitle: Text(serverId),
          ),
          ListTile(
            leading: const Icon(Icons.person),
            title: const Text('Logged in as'),
            subtitle: Text(_formatUserDisplay(user)),
          ),
          ListTile(
            leading: const Icon(Icons.security),
            title: const Text('Auth Provider'),
            subtitle: Text(config.authSystem.title),
          ),
          const Divider(),
          ListTile(
            leading: Icon(
              Icons.logout,
              color: Theme.of(context).colorScheme.error,
            ),
            title: Text(
              'Logout',
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
            onTap: () => _handleLogout(context, ref, serverId, config),
          ),
        ];

      case AppStateNoServer():
        return [
          const ListTile(
            leading: Icon(Icons.cloud_off),
            title: Text('Not Connected'),
            subtitle: Text('No server configured'),
          ),
        ];

      case AppStateProbing(:final serverId):
        return [
          ListTile(
            leading: const SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            title: const Text('Connecting...'),
            subtitle: Text(serverId),
          ),
        ];

      case AppStateNeedsAuth(:final serverId):
        return [
          ListTile(
            leading: const Icon(Icons.cloud_queue),
            title: const Text('Connected'),
            subtitle: Text(serverId),
          ),
          const ListTile(
            leading: Icon(Icons.person_off),
            title: Text('Not logged in'),
            subtitle: Text('Please log in to continue'),
          ),
        ];

      case AppStateAuthenticating(:final serverId):
        return [
          ListTile(
            leading: const SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            title: const Text('Authenticating...'),
            subtitle: Text(serverId),
          ),
        ];

      case AppStateError(:final message, :final serverId):
        return [
          ListTile(
            leading: Icon(
              Icons.error_outline,
              color: Theme.of(context).colorScheme.error,
            ),
            title: const Text('Error'),
            subtitle: Text(message),
          ),
          if (serverId != null)
            ListTile(
              leading: const Icon(Icons.dns),
              title: const Text('Server'),
              subtitle: Text(serverId),
            ),
        ];
    }
  }

  String _formatUserDisplay(UserInfo? user) {
    if (user == null) return 'Unknown user';
    if (user.name != null && user.name!.isNotEmpty) return user.name!;
    if (user.email != null && user.email!.isNotEmpty) return user.email!;
    return user.id;
  }

  Future<void> _handleLogout(
    BuildContext context,
    WidgetRef ref,
    String serverId,
    SsoConfig config,
  ) async {
    // Show confirmation dialog
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Logout'),
        content: const Text('Are you sure you want to logout?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Logout'),
          ),
        ],
      ),
    );

    if (confirmed != true || !context.mounted) return;

    // Perform logout
    final authProvider = ref.read(authProviderProvider);
    final appStateNotifier = ref.read(appStateProvider.notifier);

    try {
      await authProvider.logout(serverId, config);
      // Only the provider used for login is preserved. Multi-provider servers
      // require re-entering the server URL to see all options.
      appStateNotifier.loggedOut(
        serverId: serverId,
        providers: [config.authSystem],
      );
    } on Exception catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Logout failed: $e')),
        );
      }
    }
  }
}
