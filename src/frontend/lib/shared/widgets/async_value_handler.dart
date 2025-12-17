import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_frontend/shared/widgets/error_display.dart';
import 'package:soliplex_frontend/shared/widgets/loading_indicator.dart';

/// Widget that handles AsyncValue states with exception-aware error handling.
///
/// Automatically shows:
/// - Loading indicator during async operations
/// - Appropriate error messages based on exception type (via [ErrorDisplay])
/// - Retry button for recoverable errors
/// - Custom content when data is loaded
///
/// This widget simplifies the common pattern of handling AsyncValue in UIs:
///
/// ```dart
/// // Without AsyncValueHandler
/// final roomsAsync = ref.watch(roomsProvider);
/// return roomsAsync.when(
///   data: (rooms) => RoomsList(rooms: rooms),
///   loading: () => const LoadingIndicator(),
///   error: (error, stack) => ErrorDisplay(
///     error: error,
///     onRetry: () => ref.refresh(roomsProvider),
///   ),
/// );
///
/// // With AsyncValueHandler
/// return AsyncValueHandler<List<Room>>(
///   value: ref.watch(roomsProvider),
///   data: (rooms) => RoomsList(rooms: rooms),
///   onRetry: () => ref.refresh(roomsProvider),
/// );
/// ```
///
/// **Error Handling**: Uses [ErrorDisplay] which provides type-safe handling
/// for all exception types (NetworkException, AuthException,
/// NotFoundException, ApiException, CancelledException).
///
/// **Loading State**: Can be customized via the [loading] parameter,
/// otherwise uses the default [LoadingIndicator].
class AsyncValueHandler<T> extends StatelessWidget {
  const AsyncValueHandler({
    required this.value,
    required this.data,
    this.onRetry,
    this.loading,
    super.key,
  });

  /// The AsyncValue to handle
  final AsyncValue<T> value;

  /// Builder for the data state
  final Widget Function(T data) data;

  /// Optional retry callback for error states
  final VoidCallback? onRetry;

  /// Optional custom loading widget
  /// Defaults to [LoadingIndicator] if not provided
  final Widget? loading;

  @override
  Widget build(BuildContext context) {
    return value.when(
      data: data,
      loading: () => loading ?? const LoadingIndicator(),
      error: (error, stackTrace) => ErrorDisplay(
        error: error,
        onRetry: onRetry,
      ),
    );
  }
}
