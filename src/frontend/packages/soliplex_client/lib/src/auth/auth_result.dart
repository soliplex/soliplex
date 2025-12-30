import 'package:meta/meta.dart';
import 'package:soliplex_client/src/auth/auth_token.dart';

/// Result of checking authentication status.
///
/// Use exhaustive pattern matching to handle all cases:
/// ```dart
/// final result = await authProvider.getValidToken(serverId);
/// switch (result) {
///   case Authenticated(:final token):
///     // Use token for API calls
///   case NoToken():
///     // First-time login prompt
///   case TokenExpired():
///     // Session expired message
///   case RefreshFailed(:final cause):
///     // Log cause, redirect to login
/// }
/// ```
@immutable
sealed class AuthResult {
  const AuthResult();
}

/// User is authenticated with a valid token.
@immutable
final class Authenticated extends AuthResult {
  /// Creates an authenticated result.
  const Authenticated({required this.token});

  /// The valid authentication token.
  final AuthToken token;

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is Authenticated && other.token == token;
  }

  @override
  int get hashCode => token.hashCode;

  @override
  String toString() => 'Authenticated(token: $token)';
}

/// User is not authenticated.
///
/// Subclasses indicate why authentication is not available.
@immutable
sealed class NotAuthenticated extends AuthResult {
  const NotAuthenticated();
}

/// No token stored (never logged in or logged out).
@immutable
final class NoToken extends NotAuthenticated {
  /// Creates a no token result.
  const NoToken();

  @override
  bool operator ==(Object other) => other is NoToken;

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  String toString() => 'NoToken()';
}

/// Access token expired and no refresh token available.
@immutable
final class TokenExpired extends NotAuthenticated {
  /// Creates a token expired result.
  const TokenExpired();

  @override
  bool operator ==(Object other) => other is TokenExpired;

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  String toString() => 'TokenExpired()';
}

/// Had tokens but refresh attempt failed permanently.
///
/// This indicates the refresh token was revoked or invalidated
/// (e.g., `invalid_grant` response). The user must re-authenticate.
@immutable
final class RefreshFailed extends NotAuthenticated {
  /// Creates a refresh failed result.
  const RefreshFailed({required this.cause});

  /// The underlying error that caused the refresh to fail.
  final Object cause;

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is RefreshFailed && other.cause == cause;
  }

  @override
  int get hashCode => cause.hashCode;

  @override
  String toString() => 'RefreshFailed(cause: $cause)';
}

/// Token storage is temporarily unavailable.
///
/// This is a transient error (e.g., Keychain locked on iOS) that may
/// succeed on retry. Unlike [RefreshFailed], this does not necessarily
/// mean the user must re-authenticate.
@immutable
final class StorageUnavailable extends NotAuthenticated {
  /// Creates a storage unavailable result.
  const StorageUnavailable({required this.message});

  /// Description of the storage error.
  final String message;

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is StorageUnavailable && other.message == message;
  }

  @override
  int get hashCode => message.hashCode;

  @override
  String toString() => 'StorageUnavailable(message: $message)';
}
