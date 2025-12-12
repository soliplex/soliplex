import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/services/auth_service.dart';
import 'core/services/server_config_service.dart';
import 'features/chat/chat_screen.dart';
import 'features/server/server_setup_screen.dart';

/// Provider for tracking initialization state
final appInitializedProvider = StateProvider<bool>((ref) => false);

/// App shell that handles:
/// - Server configuration check
/// - Authentication state
/// - Navigation between setup and main app
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
    // Delay initialization to avoid modifying providers during build
    Future.microtask(_initialize);
  }

  Future<void> _initialize() async {
    try {
      // Initialize server config (loads saved servers)
      final serverConfig = ref.read(serverConfigProvider);
      await serverConfig.initialize();

      // If we have a server, initialize auth
      if (serverConfig.hasServer) {
        final authService = ref.read(authServiceProvider);
        await authService.initialize();
      }

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

    // Check server configuration
    final hasServer = ref.watch(hasServerProvider);

    if (!hasServer) {
      return ServerSetupScreen(
        onConnected: () {
          // Server connected - auth state will be updated by the auth flow
          // Just trigger rebuild by reading provider
          debugPrint('AppShell: onConnected - server connected');
          _initializeAuth();
        },
      );
    }

    // Check auth state
    final authState = ref.watch(authStateProvider);

    // If server requires auth and we're not authenticated, show setup
    if (authState.needsAuth) {
      return ServerSetupScreen(
        onConnected: () {
          // Auth state is already set by startLogin - just trigger rebuild
          // by reading the provider (the widget tree will update automatically)
          debugPrint('AppShell: onConnected - auth completed');
        },
      );
    }

    // All good - show main app
    return const ChatScreen();
  }

  Future<void> _initializeAuth() async {
    final authService = ref.read(authServiceProvider);
    await authService.initialize();
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
}
