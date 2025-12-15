import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:soliplex/core/controllers/session_lifecycle_controller.dart';
import 'package:soliplex/core/providers/app_providers.dart';

/// Provider for tracking initial app state - ensures
/// AppStateManager.initialize() is called once.
/// AppShell will watch this provider to kick off the initialization flow.
final appBootstrapperProvider = FutureProvider<void>((ref) async {
  // Ensure AppStateManager is initialized.
  await ref.read(appStateManagerProvider).initialize();
  // Ensure session lifecycle controller is active.
  // This will trigger connection manager setup, room fetching etc.
  await ref.read(sessionLifecycleProvider.future);
});

/// Extension to add server switching from anywhere in the app
extension AppShellNavigation on BuildContext {
  /// Navigate to server setup screen
  void showServerSetup() {
    go('/setup');
  }

  /// Navigate to network inspector screen
  void showNetworkInspector() {
    push('/inspector');
  }

  /// Navigate to endpoint management screen
  void showEndpointManager() {
    push('/settings');
  }
}
