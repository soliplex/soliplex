/// Interface for token refresh operations.
///
/// Decouples RefreshingHttpClient from concrete auth implementations,
/// enabling testability and following dependency inversion principle.
///
/// Frontend implementations (e.g., AuthNotifier in Flutter) implement this
/// interface to provide refresh capabilities to the HTTP client layer.
abstract interface class TokenRefresher {
  /// Whether the current token needs refresh (expiring soon or expired).
  bool get needsRefresh;

  /// Refresh tokens if they are expiring soon.
  ///
  /// Call this proactively before making API requests to avoid 401s.
  /// Does nothing if not authenticated or tokens don't need refresh.
  Future<void> refreshIfExpiringSoon();

  /// Attempt to refresh the current tokens.
  ///
  /// Returns `true` if refresh succeeded, `false` if it failed.
  /// On expired refresh token, clears auth state.
  /// On network errors, returns `false` without clearing state.
  Future<bool> tryRefresh();
}
