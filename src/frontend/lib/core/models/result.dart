import 'package:flutter/foundation.dart';

/// Result type for operations that can succeed or fail.
///
/// Use instead of returning null to signal failure.
/// Enables exhaustive pattern matching at call sites.
///
/// Example:
/// ```dart
/// final result = await doSomething();
/// switch (result) {
///   case Ok(:final value):
///     // use value
///   case Err(:final message):
///     // handle error
/// }
/// ```
@immutable
sealed class Result<T> {
  const Result();
}

/// Successful result containing a value.
@immutable
class Ok<T> extends Result<T> {
  const Ok(this.value);

  final T value;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Ok<T> &&
          runtimeType == other.runtimeType &&
          value == other.value;

  @override
  int get hashCode => value.hashCode;

  @override
  String toString() => 'Ok($value)';
}

/// Failed result containing an error message.
@immutable
class Err<T> extends Result<T> {
  const Err(this.message);

  final String message;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Err<T> &&
          runtimeType == other.runtimeType &&
          message == other.message;

  @override
  int get hashCode => message.hashCode;

  @override
  String toString() => 'Err($message)';
}
