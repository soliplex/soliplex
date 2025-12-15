import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:soliplex/core/auth/auth_providers.dart';
import 'package:soliplex/core/auth/web_auth_callback_handler.dart';
import 'package:soliplex/core/providers/app_providers.dart';
import 'package:soliplex/core/utils/debug_log.dart';

/// Screen that handles OIDC authorization callback.
///
/// When the browser redirects back from the OIDC provider, this screen:
/// 1. Shows a loading indicator
/// 2. Processes the callback (exchanges code for tokens)
/// 3. Initializes the app with the authenticated server
/// 4. Navigates to /chat on success or shows error on failure
class AuthCallbackScreen extends ConsumerStatefulWidget {
  const AuthCallbackScreen({super.key});

  @override
  ConsumerState<AuthCallbackScreen> createState() => _AuthCallbackScreenState();
}

class _AuthCallbackScreenState extends ConsumerState<AuthCallbackScreen> {
  String? _error;
  bool _isProcessing = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _processCallback();
    });
  }

  Future<void> _processCallback() async {
    DebugLog.auth('AuthCallbackScreen: Processing callback...');

    try {
      final handler = ref.read(webAuthCallbackHandlerProvider);
      final result = await handler.handleCallback();

      switch (result) {
        case AuthCallbackSuccess(:final serverId):
          DebugLog.auth('AuthCallbackScreen: Success! Server: $serverId');
          await _initializeAndNavigate(serverId);

        case AuthCallbackFailure(:final error, :final description):
          DebugLog.error('AuthCallbackScreen: Auth failed: $error');
          setState(() {
            _error = description ?? error;
            _isProcessing = false;
          });

        case AuthCallbackNotDetected():
          DebugLog.warn('AuthCallbackScreen: No callback detected');
          setState(() {
            _error = 'No authentication callback detected';
            _isProcessing = false;
          });
      }
    } on Object catch (e) {
      DebugLog.error('AuthCallbackScreen: Exception: $e');
      setState(() {
        _error = e.toString();
        _isProcessing = false;
      });
    }
  }

  Future<void> _initializeAndNavigate(String serverId) async {
    try {
      final appStateManager = ref.read(appStateManagerProvider);
      await appStateManager.initializeWithServer(serverId);

      // Wait for the stream to emit AppStateReady before navigating
      await appStateManager.state.firstWhere((state) => state is AppStateReady);

      if (mounted) {
        context.go('/chat');
      }
    } on Object catch (e) {
      DebugLog.error('AuthCallbackScreen: Failed to initialize: $e');
      setState(() {
        _error = 'Failed to initialize: $e';
        _isProcessing = false;
      });
    }
  }

  void _navigateToSetup() {
    context.go('/setup');
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 400),
          child: Card(
            margin: const EdgeInsets.all(24),
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: _isProcessing
                  ? _buildProcessing(theme)
                  : _buildError(theme),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildProcessing(ThemeData theme) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const CircularProgressIndicator(),
        const SizedBox(height: 24),
        Text(
          'Completing authentication...',
          style: theme.textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        Text(
          'Please wait while we verify your credentials.',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
          textAlign: TextAlign.center,
        ),
      ],
    );
  }

  Widget _buildError(ThemeData theme) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.error_outline, size: 48, color: theme.colorScheme.error),
        const SizedBox(height: 16),
        Text('Authentication Failed', style: theme.textTheme.titleLarge),
        const SizedBox(height: 8),
        Text(
          _error ?? 'An unknown error occurred',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 24),
        FilledButton(
          onPressed: _navigateToSetup,
          child: const Text('Back to Setup'),
        ),
      ],
    );
  }
}
