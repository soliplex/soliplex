import 'package:meta/meta.dart';
import 'package:soliplex_client/src/auth/auth_token.dart';

/// Result of reading a token from storage.
///
/// Use exhaustive pattern matching to handle both cases:
/// ```dart
/// final result = await tokenStorage.read(serverId);
/// switch (result) {
///   case TokenFound(:final token):
///     // use token
///   case TokenNotFound():
///     // no token stored
/// }
/// ```
@immutable
sealed class TokenResult {
  const TokenResult();
}

/// Token was found in storage.
@immutable
final class TokenFound extends TokenResult {
  /// Creates a token found result.
  const TokenFound(this.token);

  /// The stored token.
  final AuthToken token;

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is TokenFound && other.token == token;
  }

  @override
  int get hashCode => token.hashCode;

  @override
  String toString() => 'TokenFound($token)';
}

/// No token stored for the requested server.
@immutable
final class TokenNotFound extends TokenResult {
  /// Creates a token not found result.
  const TokenNotFound();

  @override
  bool operator ==(Object other) => other is TokenNotFound;

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  String toString() => 'TokenNotFound()';
}
