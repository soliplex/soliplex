import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_frontend/core/providers/auth_providers.dart';
import 'package:soliplex_frontend/core/state/app_state.dart';

/// Bridges Riverpod's appStateProvider to GoRouter's refreshListenable.
///
/// GoRouter requires a [Listenable] to trigger route re-evaluation.
/// This notifier listens to the Riverpod provider and notifies GoRouter
/// when the auth state changes.
class RouterNotifier extends ChangeNotifier {
  RouterNotifier(this._ref) {
    _ref.listen(appStateProvider, (_, __) => notifyListeners());
  }

  final Ref _ref;

  /// Current auth state for redirect logic.
  AppState get state => _ref.read(appStateProvider);

  /// Whether the user is authenticated.
  bool get isAuthenticated => state is AppStateReady;

  /// Whether the auth flow is in progress (probing or authenticating).
  bool get isInAuthFlow =>
      state is AppStateProbing || state is AppStateAuthenticating;
}

/// Provider for the router notifier.
///
/// Used by routerProvider to create the GoRouter with auth redirects.
final routerNotifierProvider = Provider<RouterNotifier>((ref) {
  return RouterNotifier(ref);
});
