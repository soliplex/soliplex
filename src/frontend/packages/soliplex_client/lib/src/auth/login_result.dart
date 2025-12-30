import 'package:meta/meta.dart';
import 'package:soliplex_client/src/auth/auth_token.dart';

/// Result of a login operation.
///
/// Use exhaustive pattern matching to handle both cases:
/// ```dart
/// final result = await authProvider.login(serverId, config);
/// switch (result) {
///   case LoginSuccess(:final token):
///     // Use token, authentication completed
///   case LoginRedirect(:final serverId):
///     // Browser is redirecting; wait for callback with tokens
/// }
/// ```
@immutable
sealed class LoginResult {
  const LoginResult();
}

/// Login succeeded and tokens are available.
@immutable
final class LoginSuccess extends LoginResult {
  /// Creates a success result.
  const LoginSuccess(this.token);

  /// The obtained auth token.
  final AuthToken token;

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is LoginSuccess && other.token == token;
  }

  @override
  int get hashCode => token.hashCode;

  @override
  String toString() => 'LoginSuccess($token)';
}

/// Browser redirect initiated (web/desktop backend-mediated flow).
///
/// This indicates the browser is redirecting to the OIDC provider.
/// The app will receive tokens via callback URL. Callers should handle
/// this by waiting for the callback screen to process the redirect.
@immutable
final class LoginRedirect extends LoginResult {
  /// Creates a redirect result.
  const LoginRedirect({required this.serverId});

  /// The server ID being authenticated to.
  final String serverId;

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is LoginRedirect && other.serverId == serverId;
  }

  @override
  int get hashCode => serverId.hashCode;

  @override
  String toString() => 'LoginRedirect(server: $serverId)';
}
