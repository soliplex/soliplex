import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/auth/auth_orchestrator.dart';
import 'package:soliplex_frontend/core/providers/auth_providers.dart';
import 'package:soliplex_frontend/core/router/app_router.dart';
import 'package:soliplex_frontend/core/state/app_state.dart';

// ============================================================================
// Test Fixtures - Shared auth-related constants
// ============================================================================

/// Test OIDC auth system.
///
/// Uses realistic 'Keycloak' naming for UI tests that assert on displayed text.
const testAuthSystem = OIDCAuthSystem(
  id: 'keycloak',
  title: 'Keycloak',
  serverUrl: 'https://auth.example.com',
  clientId: 'test-client',
);

/// Test SSO config.
const testSsoConfig = SsoConfig(
  authSystem: testAuthSystem,
  authorizationEndpoint: 'https://auth.example.com/authorize',
  tokenEndpoint: 'https://auth.example.com/token',
);

/// Test user info.
const testUser = UserInfo(
  id: 'user-123',
  email: 'user@example.com',
);

/// Test providers list.
const testProviders = [testAuthSystem];

/// Far-future expiration for test tokens that should never expire during tests.
final _testTokenExpiration = DateTime.utc(2099);

/// Test auth token (final, not const, because DateTime isn't compile-time).
final testToken = AuthToken(
  accessToken: 'test-access-token',
  expiresAt: _testTokenExpiration,
);

// ============================================================================
// Test Notifier - AppStateNotifier that starts in a specific state
// ============================================================================

/// Test notifier that starts in a specific state.
///
/// Used for tests that need to verify UI behavior for specific states
/// without going through the full orchestration flow. Extends the production
/// `AppStateNotifier` to allow initialization with a specific state.
class TestAppStateNotifier extends AppStateNotifier {
  /// Creates a test notifier starting in the given initial state.
  TestAppStateNotifier(this._initialState);

  final AppState _initialState;

  @override
  AppState build() => _initialState;
}

/// Creates an authenticated [AppStateReady] for tests.
AppStateReady testAuthenticatedState({
  String serverId = 'http://localhost:8000',
  SsoConfig config = testSsoConfig,
  UserInfo? user = testUser,
}) {
  return AppStateReady(
    serverId: serverId,
    config: config,
    user: user,
  );
}

// ============================================================================
// Mock Orchestrator - For testing login flows without HTTP
// ============================================================================

/// Mock orchestrator that returns configurable results.
///
/// Used for tests that need to verify login flow behavior without real
/// OIDC discovery or HTTP calls.
///
/// Configure only the results you need - unconfigured methods throw
/// [StateError] when called, catching test misuse early.
class MockAuthOrchestrator implements AuthOrchestrator {
  /// Creates a mock orchestrator with optional results.
  ///
  /// Only configure the results needed for your test. Calling a method
  /// without its result configured throws [StateError].
  MockAuthOrchestrator({this.probeResult, this.loginResult});

  /// Result returned by [probeServer], or null if not configured.
  final ProbeResult? probeResult;

  /// Result returned by [login], or null if not configured.
  final LoginAttemptResult? loginResult;

  @override
  Future<ProbeResult> probeServer(String serverUrl) async {
    final result = probeResult;
    if (result == null) {
      throw StateError(
        'MockAuthOrchestrator.probeServer() called but probeResult not '
        'configured. Provide probeResult in constructor.',
      );
    }
    return result;
  }

  @override
  Future<LoginAttemptResult> login(
    OIDCAuthSystem authSystem,
    String serverId,
  ) async {
    final result = loginResult;
    if (result == null) {
      throw StateError(
        'MockAuthOrchestrator.login() called but loginResult not configured. '
        'Provide loginResult in constructor.',
      );
    }
    return result;
  }
}

// ============================================================================
// Router Test Helpers - For testing router navigation
// ============================================================================

/// Test app that provides access to the router for navigation.
class RouterTestApp extends ConsumerStatefulWidget {
  /// Creates a test app with optional initial location.
  const RouterTestApp({super.key, this.initialLocation});

  /// The initial location to navigate to after first build.
  final String? initialLocation;

  @override
  ConsumerState<RouterTestApp> createState() => _RouterTestAppState();
}

class _RouterTestAppState extends ConsumerState<RouterTestApp> {
  late final GoRouter _router = ref.read(routerProvider);
  bool _navigated = false;

  @override
  Widget build(BuildContext context) {
    final router = _router;

    final initialLocation = widget.initialLocation;
    if (initialLocation != null && !_navigated) {
      _navigated = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        router.go(initialLocation);
      });
    }

    return MaterialApp.router(routerConfig: router);
  }
}

/// Creates a router test app with provider overrides.
Widget createRouterTestApp({
  List<dynamic> overrides = const [],
  String? initialLocation,
}) {
  return ProviderScope(
    overrides: overrides.cast(),
    child: RouterTestApp(initialLocation: initialLocation),
  );
}
