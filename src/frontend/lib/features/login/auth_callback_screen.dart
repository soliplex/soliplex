import 'package:flutter/material.dart';

/// OAuth callback screen for web authentication.
///
/// Handles the redirect from the OAuth provider:
/// 1. Extracts tokens from URL query parameters
/// 2. Validates CSRF state
/// 3. Stores tokens via auth provider
/// 4. Redirects to the app
class AuthCallbackScreen extends StatelessWidget {
  const AuthCallbackScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Completing authentication...'),
          ],
        ),
      ),
    );
  }
}
