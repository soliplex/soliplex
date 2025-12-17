import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:soliplex_client/soliplex_client.dart';

/// Standard error display widget with retry button.
///
/// Displays different error messages and icons based on exception type:
/// - [AuthException]: Shows authentication required message
/// - [NetworkException]: Differentiates timeout vs connection errors
/// - [NotFoundException]: Shows resource not found message
/// - [ApiException]: Shows server error with status code
/// - [CancelledException]: Shows operation cancelled message
/// - Unknown errors: Shows generic error message
///
/// In debug mode, shows the full error details below the message
/// for easier debugging.
class ErrorDisplay extends StatelessWidget {
  const ErrorDisplay({
    required this.error,
    this.onRetry,
    super.key,
  });

  final Object error;
  final VoidCallback? onRetry;

  String _getErrorMessage() {
    if (error is AuthException) {
      // AM1-AM6: No auth implemented yet
      // AM7+: This should trigger redirect to login
      return 'Authentication required. Coming in AM7.';
    } else if (error is NetworkException) {
      final netErr = error as NetworkException;
      if (netErr.isTimeout) {
        return 'Request timed out. Please try again.';
      }
      return 'Network error. Please check your connection.';
    } else if (error is NotFoundException) {
      final notFound = error as NotFoundException;
      if (notFound.resource != null) {
        return '${notFound.resource} not found.';
      }
      return 'Resource not found.';
    } else if (error is ApiException) {
      final apiError = error as ApiException;
      return 'Server error (${apiError.statusCode}): ${apiError.message}';
    } else if (error is CancelledException) {
      return 'Operation cancelled.';
    } else {
      return 'An unexpected error occurred.';
    }
  }

  IconData _getErrorIcon() {
    if (error is AuthException) return Icons.lock_outline;
    if (error is NetworkException) return Icons.wifi_off;
    if (error is NotFoundException) return Icons.search_off;
    if (error is CancelledException) return Icons.cancel_outlined;
    return Icons.error_outline;
  }

  bool _canRetry() {
    // AuthException should not show retry button (need login flow)
    // CancelledException should not show retry button (user cancelled)
    return error is! AuthException && error is! CancelledException;
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              _getErrorIcon(),
              size: 64,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: 16),
            Text(
              _getErrorMessage(),
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            // Debug info in development builds
            if (kDebugMode) ...[
              const SizedBox(height: 8),
              SelectableText(
                error.toString(),
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      fontFamily: 'monospace',
                      color: Colors.grey,
                    ),
              ),
            ],
            if (onRetry != null && _canRetry()) ...[
              const SizedBox(height: 16),
              ElevatedButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
