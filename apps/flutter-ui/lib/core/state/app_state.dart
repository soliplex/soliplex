import 'package:equatable/equatable.dart';

import 'package:soliplex/core/models/server_models.dart';

/// Sealed app state class for explicit state machine.
///
/// Each subclass represents a distinct application state.
/// Pattern matching ensures all states are handled.
sealed class AppState extends Equatable {
  const AppState();
}

/// No server configured - show server setup screen.
class AppStateNoServer extends AppState {
  const AppStateNoServer();

  @override
  List<Object?> get props => [];
}

/// Server configured but needs authentication.
class AppStateNeedsAuth extends AppState {
  const AppStateNeedsAuth({required this.server, required this.providers});
  final ServerConnection server;
  final List<OIDCAuthSystem> providers;

  @override
  List<Object?> get props => [server, providers];
}

/// OIDC authentication in progress.
class AppStateAuthenticating extends AppState {
  const AppStateAuthenticating({required this.server, required this.provider});
  final ServerConnection server;
  final OIDCAuthSystem provider;

  @override
  List<Object?> get props => [server, provider];
}

/// Authenticated and ready to use.
class AppStateReady extends AppState {
  const AppStateReady({required this.server, this.userName, this.userEmail});
  final ServerConnection server;
  final String? userName;
  final String? userEmail;

  @override
  List<Object?> get props => [server, userName, userEmail];
}

/// Error state with ability to retry.
class AppStateError extends AppState {
  const AppStateError(this.message, {this.previousState});
  final String message;
  final AppState? previousState;

  @override
  List<Object?> get props => [message, previousState];
}

/// Extension for convenient state checks.
extension AppStateX on AppState {
  /// Get the current server if in a state that has one.
  ServerConnection? get server => switch (this) {
    AppStateNoServer() => null,
    AppStateNeedsAuth(:final server) => server,
    AppStateAuthenticating(:final server) => server,
    AppStateReady(:final server) => server,
    AppStateError(:final previousState) => previousState?.server,
  };

  /// Whether the app is ready to use.
  bool get isReady => this is AppStateReady;

  /// Whether authentication is in progress.
  bool get isAuthenticating => this is AppStateAuthenticating;

  /// Whether authentication is needed.
  bool get needsAuth => this is AppStateNeedsAuth;

  /// Whether there's an error.
  bool get hasError => this is AppStateError;
}
