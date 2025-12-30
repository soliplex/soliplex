import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/auth/web_auth_provider.dart';
import 'package:soliplex_frontend/core/providers/auth_providers.dart';

/// OAuth callback screen for web authentication.
///
/// Handles the redirect from the OAuth provider by:
/// 1. Extracting tokens from URL query parameters
/// 2. Retrieving pending auth state (serverId + authSystem)
/// 3. Re-discovering OIDC configuration
/// 4. Storing tokens and transitioning to authenticated state
///
/// On success, navigates to the home screen.
/// On failure, navigates to login with error displayed.
class AuthCallbackScreen extends ConsumerStatefulWidget {
  /// Creates an auth callback screen.
  const AuthCallbackScreen({super.key});

  @override
  ConsumerState<AuthCallbackScreen> createState() => _AuthCallbackScreenState();
}

class _AuthCallbackScreenState extends ConsumerState<AuthCallbackScreen> {
  String? _error;
  bool _processing = true;
  String? _knownServerId;

  @override
  void initState() {
    super.initState();
    // Process callback after first frame to ensure providers are available
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _processCallback();
    });
  }

  Future<void> _processCallback() async {
    try {
      await _handleCallback();
    } on Exception catch (e) {
      _setError('Unexpected error: $e');
    }
  }

  Future<void> _handleCallback() async {
    // Extract tokens from URL query parameters
    final uri = GoRouterState.of(context).uri;
    final params = uri.queryParameters;

    final accessToken = params['token'];
    final refreshToken = params['refresh_token'];
    final expiresInStr = params['expires_in'];

    // Validate required parameters
    if (accessToken == null || accessToken.isEmpty) {
      _setError('Missing access token in callback');
      return;
    }

    if (expiresInStr == null) {
      _setError('Missing token expiration in callback');
      return;
    }

    final expiresIn = int.tryParse(expiresInStr);
    if (expiresIn == null) {
      _setError('Invalid token expiration format');
      return;
    }

    // Get pending auth state
    final pendingStorage = ref.read(pendingStorageProvider);
    final pendingResult = await pendingStorage.getPendingAuth();

    switch (pendingResult) {
      case NoPendingAuth():
        _setError('No pending authentication - please try logging in again');
        return;
      case PendingAuthFound(:final serverId, :final authSystem):
        _knownServerId = serverId;
        await _completeAuth(
          serverId: serverId,
          authSystem: authSystem,
          accessToken: accessToken,
          refreshToken: refreshToken,
          expiresIn: expiresIn,
        );
    }
  }

  Future<void> _completeAuth({
    required String serverId,
    required OIDCAuthSystem authSystem,
    required String accessToken,
    required String? refreshToken,
    required int expiresIn,
  }) async {
    // Re-discover OIDC configuration
    final discoveryService = ref.read(oidcDiscoveryServiceProvider);
    final SsoConfig config;
    try {
      config = await discoveryService.discover(authSystem);
    } on AuthError catch (e) {
      _setError('OIDC discovery failed: ${e.message}');
      return;
    }

    // Build and store token.
    // Note: expiration calculated from client clock. If client clock is
    // significantly wrong, token may appear expired prematurely or late.
    final token = AuthToken(
      accessToken: accessToken,
      refreshToken: refreshToken,
      expiresAt: DateTime.now().toUtc().add(Duration(seconds: expiresIn)),
    );

    final tokenStorage = ref.read(tokenStorageProvider);
    try {
      await tokenStorage.write(serverId, token);
    } on Exception {
      _setError('Failed to save credentials. Please try again.');
      return;
    }

    // Fetch user info (optional - don't fail if unavailable)
    UserInfo? user;
    try {
      final authProvider = ref.read(authProviderProvider);
      user = await authProvider.getCurrentUser(serverId, config);
    } on AuthError {
      // User info is optional - proceed without it
    }

    // Clear pending auth state - cleanup failure shouldn't block auth
    final pendingStorage = ref.read(pendingStorageProvider);
    try {
      await pendingStorage.clearPendingAuth();
    } on Exception {
      // Ignore: tokens are stored, user is authenticated. Orphaned pending
      // state will be overwritten on next login.
    }

    // Transition to authenticated state
    ref.read(appStateProvider.notifier).setAuthenticated(
          serverId: serverId,
          config: config,
          user: user,
        );

    // Navigate to home (no local state update needed - leaving this screen)
    if (mounted) {
      context.go('/');
    }
  }

  void _setError(String message) {
    if (mounted) {
      // Sync global state so router guards behave consistently
      ref
          .read(appStateProvider.notifier)
          .setError(message: message, serverId: _knownServerId);
      setState(() {
        _error = message;
        _processing = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    if (_processing) {
      return Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircularProgressIndicator(),
              const SizedBox(height: 24),
              Text(
                'Completing authentication...',
                style: theme.textTheme.bodyLarge,
              ),
            ],
          ),
        ),
      );
    }

    // Error state
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 400),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.error_outline,
                size: 64,
                color: theme.colorScheme.error,
              ),
              const SizedBox(height: 24),
              Text(
                'Authentication Failed',
                style: theme.textTheme.titleLarge,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              Text(
                _error ?? 'An unknown error occurred',
                style: theme.textTheme.bodyMedium,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              FilledButton.icon(
                onPressed: () => context.go('/login'),
                icon: const Icon(Icons.arrow_back),
                label: const Text('Return to login'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
