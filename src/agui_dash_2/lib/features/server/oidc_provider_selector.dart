import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/services/auth_service.dart';
import '../../core/services/server_config_service.dart';

/// Widget for selecting and initiating OIDC login.
///
/// Displays available OIDC providers as buttons and
/// handles the authentication flow.
class OIDCProviderSelector extends ConsumerStatefulWidget {
  final List<OIDCAuthSystem> providers;
  final String serverUrl;
  final VoidCallback? onAuthenticated;

  const OIDCProviderSelector({
    super.key,
    required this.providers,
    required this.serverUrl,
    this.onAuthenticated,
  });

  @override
  ConsumerState<OIDCProviderSelector> createState() =>
      _OIDCProviderSelectorState();
}

class _OIDCProviderSelectorState extends ConsumerState<OIDCProviderSelector> {
  bool _isAuthenticating = false;

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authStateProvider);
    final theme = Theme.of(context);

    debugPrint('OIDCProviderSelector build: providers=${widget.providers.length}, '
        'authStatus=${authState.status}, isAuthenticating=$_isAuthenticating');

    // Listen for auth completion
    ref.listen(authStateProvider, (previous, next) {
      debugPrint('OIDCProviderSelector: Auth state changed: ${previous?.status} -> ${next.status}');
      debugPrint('OIDCProviderSelector: isAuthenticated: ${previous?.isAuthenticated} -> ${next.isAuthenticated}');
      if (next.isAuthenticated && previous?.isAuthenticated != true) {
        debugPrint('OIDCProviderSelector: Calling onAuthenticated callback');
        widget.onAuthenticated?.call();
      }
    });

    if (widget.providers.isEmpty) {
      debugPrint('OIDCProviderSelector: No providers available');
      return Center(
        child: Text(
          'No login methods available',
          style: TextStyle(color: theme.colorScheme.error),
        ),
      );
    }

    // Show error if auth failed
    if (authState.status == AuthStatus.error) {
      debugPrint('OIDCProviderSelector: Showing error state');
      return Column(
        children: [
          _buildErrorCard(theme, authState.error ?? 'Authentication failed'),
          const SizedBox(height: 16),
          _buildProviderButtons(theme),
        ],
      );
    }

    // Show loading during auth
    if (_isAuthenticating || authState.status == AuthStatus.authenticating) {
      debugPrint('OIDCProviderSelector: Showing authenticating state');
      return Column(
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: 16),
          Text(
            'Authenticating...',
            style: theme.textTheme.bodyMedium,
          ),
          const SizedBox(height: 8),
          TextButton(
            onPressed: _cancelAuth,
            child: const Text('Cancel'),
          ),
        ],
      );
    }

    debugPrint('OIDCProviderSelector: Showing provider buttons');
    return _buildProviderButtons(theme);
  }

  Widget _buildProviderButtons(ThemeData theme) {
    debugPrint('OIDCProviderSelector: Building ${widget.providers.length} provider buttons');
    return Column(
      children: widget.providers.map((provider) {
        debugPrint('OIDCProviderSelector: Creating button for ${provider.id}');
        return Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: _OIDCProviderButton(
            provider: provider,
            onTap: () {
              debugPrint('OIDCProviderSelector: Button tapped for ${provider.id}');
              _startLogin(provider);
            },
          ),
        );
      }).toList(),
    );
  }

  Widget _buildErrorCard(ThemeData theme, String error) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: theme.colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(
            Icons.error_outline,
            color: theme.colorScheme.onErrorContainer,
            size: 20,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              error,
              style: TextStyle(color: theme.colorScheme.onErrorContainer),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _startLogin(OIDCAuthSystem provider) async {
    debugPrint('OIDCProviderSelector: Starting login with ${provider.id}');
    setState(() {
      _isAuthenticating = true;
    });

    try {
      final authService = ref.read(authServiceProvider);
      debugPrint('OIDCProviderSelector: Got auth service, calling startLogin');
      await authService.startLogin(provider);
      debugPrint('OIDCProviderSelector: startLogin completed');

      // Reset authenticating state
      if (mounted) {
        setState(() {
          _isAuthenticating = false;
        });
      }

      // Check if login succeeded and trigger callback
      if (authService.isAuthenticated) {
        debugPrint('OIDCProviderSelector: Login succeeded, calling onAuthenticated');
        widget.onAuthenticated?.call();
      } else {
        debugPrint('OIDCProviderSelector: Login completed but not authenticated, status=${authService.state.status}');
      }
    } catch (e, stack) {
      debugPrint('OIDCProviderSelector: Login failed: $e');
      debugPrint('OIDCProviderSelector: Stack: $stack');
      if (mounted) {
        setState(() {
          _isAuthenticating = false;
        });
      }
    }
  }

  void _cancelAuth() {
    setState(() {
      _isAuthenticating = false;
    });
  }
}

/// Button for a single OIDC provider
class _OIDCProviderButton extends StatelessWidget {
  final OIDCAuthSystem provider;
  final VoidCallback? onTap;

  const _OIDCProviderButton({
    required this.provider,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    // Determine icon based on provider ID
    final (IconData icon, Color? bgColor, Color? fgColor) =
        _getProviderStyle(provider.id.toLowerCase());

    return SizedBox(
      width: double.infinity,
      child: OutlinedButton(
        onPressed: onTap,
        style: OutlinedButton.styleFrom(
          backgroundColor: bgColor,
          foregroundColor: fgColor,
          padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 20),
            const SizedBox(width: 8),
            Text('Continue with ${provider.title}'),
          ],
        ),
      ),
    );
  }

  (IconData, Color?, Color?) _getProviderStyle(String providerId) {
    // Common OIDC provider styling
    switch (providerId) {
      case 'google':
        return (Icons.g_mobiledata, Colors.white, Colors.black87);
      case 'microsoft':
      case 'azure':
        return (Icons.window, const Color(0xFF00A4EF), Colors.white);
      case 'github':
        return (Icons.code, const Color(0xFF24292E), Colors.white);
      case 'gitlab':
        return (Icons.code, const Color(0xFFFC6D26), Colors.white);
      case 'keycloak':
        return (Icons.key, null, null);
      case 'okta':
        return (Icons.security, const Color(0xFF007DC1), Colors.white);
      case 'auth0':
        return (Icons.lock_outline, const Color(0xFFEB5424), Colors.white);
      default:
        return (Icons.login, null, null);
    }
  }
}

/// Compact login prompt for app bar or inline use
class CompactLoginPrompt extends ConsumerWidget {
  final VoidCallback? onLoginTap;

  const CompactLoginPrompt({
    super.key,
    this.onLoginTap,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authStateProvider);
    final theme = Theme.of(context);

    if (authState.isAuthenticated) {
      return const SizedBox.shrink();
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: theme.colorScheme.secondaryContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.login,
            size: 16,
            color: theme.colorScheme.onSecondaryContainer,
          ),
          const SizedBox(width: 8),
          Text(
            'Login required',
            style: TextStyle(
              color: theme.colorScheme.onSecondaryContainer,
              fontSize: 12,
            ),
          ),
          const SizedBox(width: 8),
          TextButton(
            onPressed: onLoginTap,
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              minimumSize: Size.zero,
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: const Text('Login'),
          ),
        ],
      ),
    );
  }
}
