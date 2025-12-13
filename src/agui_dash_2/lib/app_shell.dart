import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/providers/app_providers.dart';
import 'features/chat/chat_screen.dart';
import 'features/inspector/network_inspector_screen.dart';
import 'features/server/server_setup_screen.dart';

/// Provider for tracking initialization state
final appInitializedProvider = StateProvider<bool>((ref) => false);

/// App shell that handles:
/// - Server configuration check
/// - Authentication state
/// - Navigation between setup and main app
///
/// Uses stream-based AppState for reactive updates without cascading rebuilds.
class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  bool _isInitializing = true;
  String? _initError;

  @override
  void initState() {
    super.initState();
    Future.microtask(_initialize);
  }

  Future<void> _initialize() async {
    try {
      // Initialize the AppStateManager (loads saved server and checks auth)
      final appStateManager = ref.read(appStateManagerProvider);
      await appStateManager.initialize();

      if (mounted) {
        ref.read(appInitializedProvider.notifier).state = true;
      }
    } catch (e) {
      debugPrint('AppShell: Initialization error: $e');
      if (mounted) {
        _initError = e.toString();
      }
    } finally {
      if (mounted) {
        setState(() {
          _isInitializing = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    // Show loading during initialization
    if (_isInitializing) {
      return const Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('Loading...'),
            ],
          ),
        ),
      );
    }

    // Show error if initialization failed
    if (_initError != null) {
      return Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.error_outline,
                size: 48,
                color: Theme.of(context).colorScheme.error,
              ),
              const SizedBox(height: 16),
              Text('Failed to initialize: $_initError'),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: () {
                  setState(() {
                    _isInitializing = true;
                    _initError = null;
                  });
                  _initialize();
                },
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    // Watch app state stream
    final stateAsync = ref.watch(appStateStreamProvider);

    return stateAsync.when(
      data: (state) => _buildForState(state),
      loading: () =>
          const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (error, _) => Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.error_outline,
                size: 48,
                color: Theme.of(context).colorScheme.error,
              ),
              const SizedBox(height: 16),
              Text('Error: $error'),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: () {
                  setState(() {
                    _isInitializing = true;
                    _initError = null;
                  });
                  _initialize();
                },
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildForState(AppState state) {
    return switch (state) {
      AppStateNoServer() => ServerSetupScreen(
        onConnected: () {
          // State machine handles transitions
          debugPrint('AppShell: Server setup completed');
        },
      ),
      AppStateNeedsAuth() => ServerSetupScreen(
        onConnected: () {
          // State machine handles transitions
          debugPrint('AppShell: Auth completed');
        },
      ),
      AppStateAuthenticating() => const Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('Authenticating...'),
            ],
          ),
        ),
      ),
      AppStateReady() => const ChatScreen(),
      AppStateError(:final message, :final previousState) => Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.error_outline,
                size: 48,
                color: Theme.of(context).colorScheme.error,
              ),
              const SizedBox(height: 16),
              Text(message),
              const SizedBox(height: 16),
              if (previousState != null)
                FilledButton(
                  onPressed: () {
                    ref.read(appStateManagerProvider).retryFromError();
                  },
                  child: const Text('Retry'),
                ),
            ],
          ),
        ),
      ),
    };
  }
}

/// Extension to add server switching from anywhere in the app
extension AppShellNavigation on BuildContext {
  /// Navigate to server setup screen
  void showServerSetup() {
    Navigator.of(this).push(
      MaterialPageRoute(
        builder: (routeContext) => ServerSetupScreen(
          onConnected: () => Navigator.of(routeContext).pop(),
        ),
      ),
    );
  }

  /// Navigate to network inspector screen
  void showNetworkInspector() {
    Navigator.of(this).push(
      MaterialPageRoute(
        builder: (routeContext) => const NetworkInspectorScreen(),
      ),
    );
  }
}
