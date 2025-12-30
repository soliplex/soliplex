import 'package:meta/meta.dart';
import 'package:soliplex_client/src/auth/auth_token.dart';

/// Result of a token refresh attempt.
///
/// Used by auth provider implementations to represent refresh outcomes.
@immutable
sealed class RefreshResult {
  const RefreshResult();
}

/// Token refresh succeeded.
@immutable
final class RefreshSuccess extends RefreshResult {
  /// Creates a success result.
  const RefreshSuccess(this.token);

  /// The refreshed token.
  final AuthToken token;
}

/// Token refresh was rejected by the server.
@immutable
final class RefreshRejected extends RefreshResult {
  /// Creates a rejected result.
  const RefreshRejected(this.cause);

  /// Description of why refresh was rejected.
  final String cause;
}
