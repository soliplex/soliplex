import 'dart:async';

import 'package:soliplex_client/src/errors/exceptions.dart';

/// Token for cancelling in-flight HTTP requests.
///
/// A [CancelToken] can be passed to HTTP transport methods to enable
/// cancellation. When [cancel] is called, any pending request associated
/// with this token will throw a [CancelledException].
///
/// Each token is single-use: once cancelled, it cannot be un-cancelled.
///
/// Example:
/// ```dart
/// final token = CancelToken();
///
/// // Start a request
/// final future = transport.request('GET', uri, cancelToken: token);
///
/// // Cancel if needed
/// token.cancel('User navigated away');
///
/// // The request will throw CancelledException
/// try {
///   await future;
/// } on CancelledException catch (e) {
///   print('Cancelled: ${e.reason}');
/// }
/// ```
class CancelToken {
  /// Creates a cancel token.
  CancelToken();

  final Completer<void> _completer = Completer<void>();
  String? _reason;

  /// Whether this token has been cancelled.
  bool get isCancelled => _completer.isCompleted;

  /// The reason provided when [cancel] was called, if any.
  String? get reason => _reason;

  /// A future that completes when [cancel] is called.
  ///
  /// Useful for listening to cancellation:
  /// ```dart
  /// token.whenCancelled.then((_) => cleanup());
  /// ```
  Future<void> get whenCancelled => _completer.future;

  /// Cancels this token with an optional [reason].
  ///
  /// If the token is already cancelled, this method does nothing.
  /// The [reason] is only stored on the first call to [cancel].
  void cancel([String? reason]) {
    if (!_completer.isCompleted) {
      _reason = reason;
      _completer.complete();
    }
  }

  /// Throws [CancelledException] if this token has been cancelled.
  ///
  /// Use this for early bailout checks:
  /// ```dart
  /// token.throwIfCancelled();
  /// await doSomeWork();
  /// token.throwIfCancelled();
  /// await doMoreWork();
  /// ```
  void throwIfCancelled() {
    if (isCancelled) {
      throw CancelledException(reason: _reason);
    }
  }
}
