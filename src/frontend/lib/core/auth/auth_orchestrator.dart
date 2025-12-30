import 'package:http/http.dart' as http;
import 'package:soliplex_client/soliplex_client.dart';

/// Result of probing a server for auth providers.
sealed class ProbeResult {
  const ProbeResult();
}

/// Server probe succeeded with available providers.
final class ProbeSuccess extends ProbeResult {
  const ProbeSuccess({required this.providers});
  final List<OIDCAuthSystem> providers;
}

/// Server probe failed.
final class ProbeFailure extends ProbeResult {
  const ProbeFailure({required this.message});
  final String message;
}

/// Result of a login attempt.
sealed class LoginAttemptResult {
  const LoginAttemptResult();
}

/// Login completed successfully (mobile flow).
final class LoginAttemptSuccess extends LoginAttemptResult {
  const LoginAttemptSuccess({required this.config, this.user});
  final SsoConfig config;
  final UserInfo? user;
}

/// Login initiated redirect (web flow).
///
/// The callback handler will need to re-discover OIDC config since
/// state isn't preserved across browser redirects.
final class LoginAttemptRedirect extends LoginAttemptResult {
  const LoginAttemptRedirect();
}

/// Login failed.
final class LoginAttemptFailure extends LoginAttemptResult {
  const LoginAttemptFailure({required this.message});
  final String message;
}

/// Orchestrates authentication flows.
///
/// Coordinates between [AuthApi], [OidcDiscoveryService], and [AuthProvider]
/// to perform server probing and login. Returns results that callers can
/// use to update state.
///
/// This class has no state - it's a pure coordinator.
class AuthOrchestrator {
  /// Creates an auth orchestrator.
  AuthOrchestrator({
    required AuthApi authApi,
    required OidcDiscoveryService discoveryService,
    required AuthProvider authProvider,
  })  : _authApi = authApi,
        _discoveryService = discoveryService,
        _authProvider = authProvider;

  final AuthApi _authApi;
  final OidcDiscoveryService _discoveryService;
  final AuthProvider _authProvider;

  /// Probes a server for available auth providers.
  ///
  /// Returns [ProbeSuccess] with providers, or [ProbeFailure] with error.
  Future<ProbeResult> probeServer(String serverUrl) async {
    try {
      final providers = await _authApi.getAuthProviders(serverUrl);

      if (providers.isEmpty) {
        return const ProbeFailure(
          message: 'No authentication providers available',
        );
      }

      return ProbeSuccess(providers: providers);
    } on ApiException catch (e) {
      return ProbeFailure(message: e.message);
    } on http.ClientException catch (e) {
      return ProbeFailure(message: 'Connection failed: ${e.message}');
    } on FormatException {
      return const ProbeFailure(message: 'Invalid server response');
    } on Exception catch (e) {
      return ProbeFailure(message: _formatExceptionMessage(e));
    }
  }

  /// Initiates login with the given auth system.
  ///
  /// Returns:
  /// - [LoginAttemptSuccess] when login completes (mobile flow)
  /// - [LoginAttemptRedirect] when browser redirect initiated (web flow)
  /// - [LoginAttemptFailure] on error
  Future<LoginAttemptResult> login(
    OIDCAuthSystem authSystem,
    String serverId,
  ) async {
    // Discover OIDC configuration
    final SsoConfig config;
    try {
      config = await _discoveryService.discover(authSystem);
    } on AuthError catch (e) {
      return LoginAttemptFailure(
        message: 'OIDC discovery failed: ${e.message}',
      );
    } on Exception catch (e) {
      return LoginAttemptFailure(
        message: 'OIDC discovery failed: ${_formatExceptionMessage(e)}',
      );
    }

    // Start login flow
    try {
      final result = await _authProvider.login(serverId, config);

      switch (result) {
        case LoginSuccess():
          // Mobile flow: token returned directly
          final user = await _authProvider.getCurrentUser(serverId, config);
          return LoginAttemptSuccess(config: config, user: user);
        case LoginRedirect():
          // Web flow: browser redirecting, callback screen will handle it
          return const LoginAttemptRedirect();
      }
    } on AuthError catch (e) {
      return LoginAttemptFailure(message: e.message);
    } on Exception catch (e) {
      return LoginAttemptFailure(message: _formatExceptionMessage(e));
    }
  }

  /// Formats an exception message for user display.
  ///
  /// Strips common exception type prefixes to produce cleaner user-facing
  /// error messages. For example:
  /// - `Exception: foo` → `foo`
  /// - `FormatException: bar` → `bar`
  String _formatExceptionMessage(Exception e) {
    // Strip common exception prefixes for cleaner user-facing messages.
    // The pattern matches "TypeName: " at the start of the message.
    return e.toString().replaceFirst(RegExp(r'^\w+Exception: '), '');
  }
}
