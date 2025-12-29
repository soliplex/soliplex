import 'package:meta/meta.dart';

/// Authentication errors for OIDC flow failures.
///
/// These are distinct from `SoliplexException` subtypes which represent
/// HTTP-level failures. AuthError represents failures during the OAuth
/// authentication flow itself (user cancelled, CSRF mismatch, etc).
@immutable
sealed class AuthError implements Exception {
  /// Creates an auth error.
  const AuthError({
    required this.message,
    this.originalError,
    this.stackTrace,
  });

  /// Error message.
  final String message;

  /// The original error that caused this, if any.
  final Object? originalError;

  /// Stack trace from the original error, if any.
  final StackTrace? stackTrace;
}

/// Authentication was cancelled by the user.
@immutable
final class AuthErrorCancelled extends AuthError {
  /// Creates a cancelled error.
  const AuthErrorCancelled({
    super.message = 'Authentication cancelled',
    super.originalError,
    super.stackTrace,
  });

  @override
  String toString() => 'AuthError.Cancelled: $message';
}

/// Network error during authentication.
@immutable
final class AuthErrorNetwork extends AuthError {
  /// Creates a network error.
  const AuthErrorNetwork({
    required super.message,
    this.isTimeout = false,
    super.originalError,
    super.stackTrace,
  });

  /// Whether this was a timeout error.
  final bool isTimeout;

  @override
  String toString() => 'AuthError.Network: $message';
}

/// CSRF state validation failed.
@immutable
final class AuthErrorInvalidState extends AuthError {
  /// Creates an invalid state error.
  const AuthErrorInvalidState({
    super.message = 'Invalid CSRF state',
    super.originalError,
    super.stackTrace,
  });

  @override
  String toString() => 'AuthError.InvalidState: $message';
}

/// Server returned an error response.
@immutable
final class AuthErrorServer extends AuthError {
  /// Creates a server error.
  const AuthErrorServer({
    required super.message,
    required this.statusCode,
    this.body,
    super.originalError,
    super.stackTrace,
  });

  /// HTTP status code.
  final int statusCode;

  /// Response body, if available.
  final String? body;

  @override
  String toString() => 'AuthError.Server($statusCode): $message';
}

/// Configuration error (missing client ID, invalid redirect URI, etc).
@immutable
final class AuthErrorConfiguration extends AuthError {
  /// Creates a configuration error.
  const AuthErrorConfiguration({
    required super.message,
    super.originalError,
    super.stackTrace,
  });

  @override
  String toString() => 'AuthError.Configuration: $message';
}

/// Operation requires authentication but user is not logged in.
@immutable
final class AuthErrorNotAuthenticated extends AuthError {
  /// Creates a not authenticated error.
  const AuthErrorNotAuthenticated({
    super.message = 'Not authenticated',
    super.originalError,
    super.stackTrace,
  });

  @override
  String toString() => 'AuthError.NotAuthenticated: $message';
}
