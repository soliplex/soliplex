import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:soliplex_frontend/core/auth/auth_flow.dart' show AuthException;
import 'package:soliplex_frontend/core/auth/auth_provider.dart';
import 'package:soliplex_frontend/core/auth/web_auth_callback.dart';

/// Screen that handles OAuth callback from web BFF flow.
///
/// Extracts tokens from URL, saves them, and navigates to home.
/// Shows error message if authentication failed.
class AuthCallbackScreen extends ConsumerStatefulWidget {
  const AuthCallbackScreen({super.key});

  @override
  ConsumerState<AuthCallbackScreen> createState() => _AuthCallbackScreenState();
}

class _AuthCallbackScreenState extends ConsumerState<AuthCallbackScreen> {
  String? _error;
  bool _processing = true;

  @override
  void initState() {
    super.initState();
    _processCallback();
  }

  Future<void> _processCallback() async {
    debugPrint('AuthCallbackScreen: Processing callback');

    final params = ref.read(capturedCallbackParamsProvider);
    debugPrint('AuthCallbackScreen: Params type: ${params.runtimeType}');

    switch (params) {
      case WebCallbackParams(:final error?, :final errorDescription):
        // OAuth error
        setState(() {
          _error = errorDescription ?? error;
          _processing = false;
        });

      case WebCallbackParams(
          accessToken: final token?,
          :final refreshToken,
          :final expiresIn,
        ):
        // Success - complete authentication
        debugPrint('AuthCallbackScreen: Got tokens, completing auth');
        await _completeAuth(
          accessToken: token,
          refreshToken: refreshToken,
          expiresIn: expiresIn,
        );

      case WebCallbackParams(accessToken: null):
        // Token missing
        setState(() {
          _error = 'Authentication failed: missing token';
          _processing = false;
        });

      case NoCallbackParams():
        // Not a callback URL - shouldn't happen in normal flow
        setState(() {
          _error = 'Invalid callback: no authentication data';
          _processing = false;
        });
    }
  }

  Future<void> _completeAuth({
    required String accessToken,
    String? refreshToken,
    int? expiresIn,
  }) async {
    debugPrint('AuthCallbackScreen: _completeAuth called');
    try {
      await ref.read(authProvider.notifier).completeWebAuth(
            accessToken: accessToken,
            refreshToken: refreshToken,
            expiresIn: expiresIn,
          );
      debugPrint('AuthCallbackScreen: completeWebAuth succeeded');

      if (mounted) {
        debugPrint('AuthCallbackScreen: Navigating to /');
        context.go('/');
      }
    } on AuthException catch (e) {
      debugPrint('AuthCallbackScreen: Auth error: ${e.message}');
      if (mounted) {
        setState(() {
          _error = e.message;
          _processing = false;
        });
      }
    } on Exception catch (e) {
      debugPrint(
        'AuthCallbackScreen: completeWebAuth failed: ${e.runtimeType}',
      );
      if (mounted) {
        setState(() {
          _error = 'Failed to complete authentication. Please try again.';
          _processing = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_processing) {
      return const Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('Completing sign in...'),
            ],
          ),
        ),
      );
    }

    // Error state
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.error_outline,
                size: 48,
                color: Theme.of(context).colorScheme.error,
              ),
              const SizedBox(height: 16),
              Text(
                'Sign In Failed',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              Text(
                _error ?? 'An unknown error occurred',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: () => context.go('/login'),
                child: const Text('Back to Login'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
