import 'package:meta/meta.dart';
import 'package:soliplex_client/soliplex_client.dart';

/// Application authentication state.
///
/// This is a sealed class hierarchy representing the app's auth status:
/// - [AppStateNoServer]: No server configured
/// - [AppStateNeedsAuth]: Server configured but not authenticated
/// - [AppStateAuthenticating]: Auth flow in progress
/// - [AppStateReady]: Authenticated and ready
/// - [AppStateError]: Error occurred
///
/// Use pattern matching for exhaustive handling:
/// ```dart
/// switch (state) {
///   case AppStateNoServer():
///     // Show server configuration
///   case AppStateNeedsAuth(:final serverId, :final providers):
///     // Show login options
///   case AppStateAuthenticating(:final serverId):
///     // Show loading indicator
///   case AppStateReady(:final serverId, :final user):
///     // Show main app
///   case AppStateError(:final message):
///     // Show error
/// }
/// ```
@immutable
sealed class AppState {
  const AppState();
}

/// No server has been configured.
///
/// The app needs a server URL before authentication can proceed.
@immutable
final class AppStateNoServer extends AppState {
  const AppStateNoServer();

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is AppStateNoServer;

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  String toString() => 'AppStateNoServer()';
}

/// Server is configured but user is not authenticated.
///
/// Contains the server ID and available authentication providers.
@immutable
final class AppStateNeedsAuth extends AppState {
  /// Creates a needs-auth state.
  const AppStateNeedsAuth({
    required this.serverId,
    required this.providers,
  });

  /// The server ID (URL) that needs authentication.
  final String serverId;

  /// Available OIDC providers for this server.
  final List<OIDCAuthSystem> providers;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is AppStateNeedsAuth &&
          serverId == other.serverId &&
          _listEquals(providers, other.providers);

  @override
  int get hashCode => Object.hash(serverId, Object.hashAll(providers));

  @override
  String toString() =>
      'AppStateNeedsAuth(serverId: $serverId, providers: ${providers.length})';
}

/// Authentication flow is in progress.
///
/// The user has initiated login and we're waiting for the flow to complete.
@immutable
final class AppStateAuthenticating extends AppState {
  const AppStateAuthenticating({required this.serverId});

  /// The server ID being authenticated to.
  final String serverId;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is AppStateAuthenticating && serverId == other.serverId;

  @override
  int get hashCode => Object.hash(runtimeType, serverId);

  @override
  String toString() => 'AppStateAuthenticating(serverId: $serverId)';
}

/// User is authenticated and the app is ready.
///
/// Contains the server ID, OIDC config for token operations, and user info.
@immutable
final class AppStateReady extends AppState {
  const AppStateReady({
    required this.serverId,
    required this.config,
    this.user,
  });

  /// The server ID the user is authenticated to.
  final String serverId;

  /// The OIDC configuration for token operations.
  final SsoConfig config;

  /// The authenticated user's info, if available.
  final UserInfo? user;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is AppStateReady &&
          serverId == other.serverId &&
          config == other.config &&
          user == other.user;

  @override
  int get hashCode => Object.hash(serverId, config, user);

  @override
  String toString() =>
      'AppStateReady(serverId: $serverId, config: $config, user: $user)';
}

/// An error occurred during authentication.
///
/// The error message describes what went wrong. The optional [serverId]
/// indicates which server the error relates to.
@immutable
final class AppStateError extends AppState {
  const AppStateError({
    required this.message,
    this.serverId,
  });

  /// Description of what went wrong.
  final String message;

  /// The server ID where the error occurred, if applicable.
  final String? serverId;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is AppStateError &&
          message == other.message &&
          serverId == other.serverId;

  @override
  int get hashCode => Object.hash(message, serverId);

  @override
  String toString() {
    final serverPart = serverId != null ? ', serverId: $serverId' : '';
    return 'AppStateError(message: $message$serverPart)';
  }
}

/// Helper for list equality comparison.
bool _listEquals<T>(List<T> a, List<T> b) {
  if (identical(a, b)) return true;
  if (a.length != b.length) return false;
  for (var i = 0; i < a.length; i++) {
    if (a[i] != b[i]) return false;
  }
  return true;
}
