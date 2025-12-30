import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

/// OAuth callback screen for web authentication.
///
/// **Status: Not yet implemented.**
///
/// When implemented, this screen will handle the redirect from the OAuth
/// provider by:
/// 1. Extracting tokens from URL query parameters
/// 2. Validating CSRF state
/// 3. Storing tokens via auth provider
/// 4. Redirecting to the app
///
/// Currently, web OAuth flows that redirect here will see an error message
/// prompting the user to return to login. The mobile OAuth flow (via
/// flutter_appauth) handles callbacks differently and does not use this screen.
class AuthCallbackScreen extends StatelessWidget {
  const AuthCallbackScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 400),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.warning_amber_rounded,
                size: 64,
                color: theme.colorScheme.error,
              ),
              const SizedBox(height: 24),
              Text(
                'Web authentication callback not implemented',
                style: theme.textTheme.titleLarge,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              Text(
                'The web OAuth flow is not yet complete. '
                'Please use mobile authentication or contact support.',
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
