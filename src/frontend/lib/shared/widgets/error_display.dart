import 'package:flutter/material.dart';
import 'package:soliplex_client/soliplex_client.dart';

/// Standard error display widget with retry button.
class ErrorDisplay extends StatelessWidget {
  const ErrorDisplay({
    required this.error,
    this.onRetry,
    super.key,
  });

  final Object error;
  final VoidCallback? onRetry;

  String _getErrorMessage() {
    if (error is NetworkException) {
      return 'Network error. Please check your connection.';
    } else if (error is NotFoundException) {
      return 'Resource not found.';
    } else if (error is ApiException) {
      final apiError = error as ApiException;
      return 'Server error (${apiError.statusCode}): ${apiError.message}';
    } else {
      return 'An unexpected error occurred.';
    }
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
              Icons.error_outline,
              size: 64,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: 16),
            Text(
              _getErrorMessage(),
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            if (onRetry != null) ...[
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
