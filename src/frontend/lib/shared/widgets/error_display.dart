import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/thread_message_cache.dart';

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

  /// Unwraps wrapper exceptions to get the underlying cause.
  Object _unwrapError() {
    if (error is MessageFetchException) {
      return (error as MessageFetchException).cause;
    }
    return error;
  }

  String _getErrorMessage() {
    final unwrapped = _unwrapError();
    if (unwrapped is AuthException) {
      // AM1-AM6: No auth implemented yet
      // AM7+: This should trigger redirect to login
      return 'Authentication required. Coming in AM7.';
    } else if (unwrapped is NetworkException) {
      final netErr = unwrapped;
      if (netErr.isTimeout) {
        return 'Request timed out. Please try again.';
      }
      return 'Network error. Please check your connection.';
    } else if (unwrapped is NotFoundException) {
      final notFound = unwrapped;
      if (notFound.resource != null) {
        return '${notFound.resource} not found.';
      }
      return 'Resource not found.';
    } else if (unwrapped is ApiException) {
      final apiError = unwrapped;
      return 'Server error (${apiError.statusCode}): ${apiError.message}';
    } else if (unwrapped is CancelledException) {
      return 'Operation cancelled.';
    } else {
      return 'An unexpected error occurred.';
    }
  }

  IconData _getErrorIcon() {
    final unwrapped = _unwrapError();
    if (unwrapped is AuthException) return Icons.lock_outline;
    if (unwrapped is NetworkException) return Icons.wifi_off;
    if (unwrapped is NotFoundException) return Icons.search_off;
    if (unwrapped is CancelledException) return Icons.cancel_outlined;
    return Icons.error_outline;
  }

  bool _canRetry() {
    final unwrapped = _unwrapError();
    // AuthException should not show retry button (need login flow)
    // CancelledException should not show retry button (user cancelled)
    return unwrapped is! AuthException && unwrapped is! CancelledException;
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ExcludeSemantics(
              child: Icon(
                _getErrorIcon(),
                size: 64,
                color: Theme.of(context).colorScheme.error,
              ),
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
