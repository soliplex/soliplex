import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/models/server_models.dart';
import 'package:soliplex/core/providers/app_providers.dart';

/// Widget for selecting and initiating OIDC login.
///
/// Displays available OIDC providers as buttons and
/// handles the authentication flow.
class OIDCProviderSelector extends ConsumerStatefulWidget {
  const OIDCProviderSelector({
    required this.providers,
    required this.serverUrl,
    super.key,
    this.onAuthenticated,
  });
  final List<OIDCAuthSystem> providers;
  final String serverUrl;
  final VoidCallback? onAuthenticated;

  @override
  ConsumerState<OIDCProviderSelector> createState() =>
      _OIDCProviderSelectorState();
}

class _OIDCProviderSelectorState extends ConsumerState<OIDCProviderSelector> {
  bool _isAuthenticating = false;
  bool _hasCalledOnAuthenticated = false;

  @override
  Widget build(BuildContext context) {
    ref.listen(appStateStreamProvider, (previous, next) {
      final nextState = next.valueOrNull;
      if (nextState is AppStateReady && !_hasCalledOnAuthenticated) {
        _hasCalledOnAuthenticated = true;
        debugPrint('OIDCProviderSelector: Calling onAuthenticated callback');
        widget.onAuthenticated?.call();
      }
    });

    final appStateAsync = ref.watch(appStateStreamProvider);
    final theme = Theme.of(context);

    debugPrint(
      'OIDCProviderSelector build: providers=${widget.providers.length}, '
      'isAuthenticating=$_isAuthenticating',
    );

    if (widget.providers.isEmpty) {
      debugPrint('OIDCProviderSelector: No providers available');
      return Center(
        child: Text(
          'No login methods available',
          style: TextStyle(color: theme.colorScheme.error),
        ),
      );
    }

    return appStateAsync.when(
      data: (state) => _buildForState(state, theme),
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => _buildErrorCard(theme, e.toString()),
    );
  }

  Widget _buildForState(AppState state, ThemeData theme) {
    // Show error if auth failed
    if (state is AppStateError) {
      debugPrint('OIDCProviderSelector: Showing error state');
      return Column(
        children: [
          _buildErrorCard(theme, state.message),
          const SizedBox(height: 16),
          _buildProviderButtons(theme),
        ],
      );
    }

    // Show loading during auth
    if (_isAuthenticating || state is AppStateAuthenticating) {
      debugPrint('OIDCProviderSelector: Showing authenticating state');
      return Column(
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: 16),
          Text('Authenticating...', style: theme.textTheme.bodyMedium),
          const SizedBox(height: 8),
          TextButton(onPressed: _cancelAuth, child: const Text('Cancel')),
        ],
      );
    }

    debugPrint('OIDCProviderSelector: Showing provider buttons');
    return _buildProviderButtons(theme);
  }

  Widget _buildProviderButtons(ThemeData theme) {
    debugPrint(
      // ignore: lines_longer_than_80_chars (auto-documented)
      'OIDCProviderSelector: Building ${widget.providers.length} provider buttons',
    );
    return Column(
      children: widget.providers.map((provider) {
        debugPrint('OIDCProviderSelector: Creating button for ${provider.id}');
        return Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: _OIDCProviderButton(
            provider: provider,
            onTap: () {
              debugPrint(
                'OIDCProviderSelector: Button tapped for ${provider.id}',
              );
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
      final appStateManager = ref.read(appStateManagerProvider);
      debugPrint(
        'OIDCProviderSelector: Got app state manager, calling startLogin',
      );
      await appStateManager.startLogin(provider);
      debugPrint('OIDCProviderSelector: startLogin completed');

      // Reset authenticating state - callback handled by ref.listen
      if (mounted) {
        setState(() {
          _isAuthenticating = false;
        });
      }
    } on Object catch (e, stack) {
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
  const _OIDCProviderButton({required this.provider, this.onTap});
  final OIDCAuthSystem provider;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    // Determine icon based on provider ID
    final (IconData icon, Color? bgColor, Color? fgColor) = _getProviderStyle(
      provider.id.toLowerCase(),
    );

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
            Text(provider.title),
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
  const CompactLoginPrompt({super.key, this.onLoginTap});
  final VoidCallback? onLoginTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final appStateAsync = ref.watch(appStateStreamProvider);
    final theme = Theme.of(context);

    final isReady = appStateAsync.whenOrNull(data: (s) => s.isReady) ?? false;

    if (isReady) {
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
