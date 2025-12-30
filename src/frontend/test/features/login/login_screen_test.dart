import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/auth/auth_orchestrator.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';
import 'package:soliplex_frontend/core/providers/auth_providers.dart';
import 'package:soliplex_frontend/core/state/app_state.dart';
import 'package:soliplex_frontend/features/login/login_screen.dart';

import '../../helpers/auth_test_helpers.dart';

/// JSON representation of [testProviders] for HTTP response mocking.
final testProvidersJson = testProviders.map((p) => p.toJson()).toList();

/// Creates a mock HTTP client for testing.
MockClient _createMockClient({
  int statusCode = 200,
  Object? body,
  void Function(http.Request)? onRequest,
}) {
  return MockClient((request) async {
    onRequest?.call(request);
    return http.Response(
      body != null ? jsonEncode(body) : '',
      statusCode,
    );
  });
}

/// Creates a test widget with the login screen.
Widget createLoginScreenApp({
  List<dynamic> overrides = const [],
}) {
  return ProviderScope(
    overrides: overrides.cast(),
    child: const MaterialApp(home: LoginScreen()),
  );
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('LoginScreen - Initial State', () {
    testWidgets('displays server URL input and connect button', (tester) async {
      await tester.pumpWidget(createLoginScreenApp());
      await tester.pumpAndSettle();

      expect(find.text('Soliplex'), findsOneWidget);
      expect(find.text('Connect to a server to get started'), findsOneWidget);
      expect(find.byType(TextFormField), findsOneWidget);
      expect(find.text('Connect'), findsOneWidget);
    });

    testWidgets('pre-fills server URL from config', (tester) async {
      await tester.pumpWidget(createLoginScreenApp());
      await tester.pumpAndSettle();

      final textField =
          tester.widget<TextFormField>(find.byType(TextFormField));
      expect(
        textField.controller?.text,
        equals('http://localhost:8000'),
      );
    });

    testWidgets('shows providers when AppStateNeedsAuth', (tester) async {
      await tester.pumpWidget(
        createLoginScreenApp(
          overrides: [
            appStateProvider.overrideWith(
              () => TestAppStateNotifier(
                const AppStateNeedsAuth(
                  serverId: 'https://api.example.com',
                  providers: testProviders,
                ),
              ),
            ),
          ],
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Sign in with'), findsOneWidget);
      expect(find.text('Keycloak'), findsOneWidget);
    });
  });

  group('LoginScreen - Validation', () {
    testWidgets('shows error for empty URL', (tester) async {
      await tester.pumpWidget(createLoginScreenApp());
      await tester.pumpAndSettle();

      // Clear the text field
      await tester.enterText(find.byType(TextFormField), '');
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      expect(find.text('Server URL is required'), findsOneWidget);
    });

    testWidgets('shows error for invalid URL scheme', (tester) async {
      await tester.pumpWidget(createLoginScreenApp());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField), 'ftp://server.com');
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      expect(
        find.text('URL must start with http:// or https://'),
        findsOneWidget,
      );
    });

    testWidgets('accepts valid http URL', (tester) async {
      final mockClient = _createMockClient(body: testProvidersJson);

      await tester.pumpWidget(
        createLoginScreenApp(
          overrides: [
            httpClientProvider.overrideWithValue(mockClient),
          ],
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byType(TextFormField),
        'http://localhost:8000',
      );
      await tester.tap(find.text('Connect'));
      await tester.pump();

      // Should not show validation error
      expect(find.text('Server URL is required'), findsNothing);
      expect(
        find.text('URL must start with http:// or https://'),
        findsNothing,
      );
    });

    testWidgets('accepts valid https URL', (tester) async {
      final mockClient = _createMockClient(body: testProvidersJson);

      await tester.pumpWidget(
        createLoginScreenApp(
          overrides: [
            httpClientProvider.overrideWithValue(mockClient),
          ],
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byType(TextFormField),
        'https://api.example.com',
      );
      await tester.tap(find.text('Connect'));
      await tester.pump();

      expect(find.text('Server URL is required'), findsNothing);
      expect(
        find.text('URL must start with http:// or https://'),
        findsNothing,
      );
    });
  });

  group('LoginScreen - Server Probing', () {
    testWidgets('shows loading indicator while probing', (tester) async {
      // Use a completer to control when the response is returned
      final completer = Completer<http.Response>();
      final mockClient = MockClient((request) => completer.future);

      await tester.pumpWidget(
        createLoginScreenApp(
          overrides: [
            httpClientProvider.overrideWithValue(mockClient),
          ],
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Connect'));
      await tester.pump();

      // Should show loading indicator
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      // Complete the future to clean up
      completer.complete(http.Response(jsonEncode(testProvidersJson), 200));
      await tester.pumpAndSettle();
    });

    testWidgets('shows providers after successful probe', (tester) async {
      final mockClient = _createMockClient(
        body: [
          testAuthSystem.toJson(),
          const OIDCAuthSystem(
            id: 'azure',
            title: 'Azure AD',
            serverUrl: 'https://login.microsoft.com',
            clientId: 'azure-client',
          ).toJson(),
        ],
      );

      await tester.pumpWidget(
        createLoginScreenApp(
          overrides: [
            httpClientProvider.overrideWithValue(mockClient),
          ],
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      expect(find.text('Sign in with'), findsOneWidget);
      expect(find.text('Keycloak'), findsOneWidget);
      expect(find.text('Azure AD'), findsOneWidget);
    });

    testWidgets('shows error for server failure', (tester) async {
      final mockClient = _createMockClient(statusCode: 500);

      await tester.pumpWidget(
        createLoginScreenApp(
          overrides: [
            httpClientProvider.overrideWithValue(mockClient),
          ],
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      expect(find.textContaining('returned 500'), findsOneWidget);
    });

    testWidgets('shows error for empty provider list', (tester) async {
      final mockClient = _createMockClient(body: <dynamic>[]);

      await tester.pumpWidget(
        createLoginScreenApp(
          overrides: [
            httpClientProvider.overrideWithValue(mockClient),
          ],
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      expect(
        find.text('No authentication providers available'),
        findsOneWidget,
      );
    });

    testWidgets('probes correct URL', (tester) async {
      Uri? probedUri;
      final mockClient = _createMockClient(
        body: testProviders,
        onRequest: (request) {
          probedUri = request.url;
        },
      );

      await tester.pumpWidget(
        createLoginScreenApp(
          overrides: [
            httpClientProvider.overrideWithValue(mockClient),
          ],
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byType(TextFormField),
        'https://api.example.com',
      );
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      expect(
        probedUri?.toString(),
        equals('https://api.example.com/api/login'),
      );
    });

    testWidgets('shows orchestrator probe failure in UI', (tester) async {
      final mockOrchestrator = MockAuthOrchestrator(
        probeResult: const ProbeFailure(message: 'Server unreachable'),
      );

      await tester.pumpWidget(
        createLoginScreenApp(
          overrides: [
            authOrchestratorProvider.overrideWithValue(mockOrchestrator),
          ],
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      expect(find.text('Server unreachable'), findsOneWidget);
    });
  });

  group('LoginScreen - Error Display', () {
    testWidgets('shows error from AppStateError', (tester) async {
      await tester.pumpWidget(
        createLoginScreenApp(
          overrides: [
            appStateProvider.overrideWith(
              () => TestAppStateNotifier(
                const AppStateError(
                  message: 'Authentication failed',
                  serverId: 'https://api.example.com',
                ),
              ),
            ),
          ],
        ),
      );
      await tester.pumpAndSettle();

      // Error message should be displayed
      expect(find.text('Authentication failed'), findsOneWidget);

      // Server URL should be pre-filled from error state
      final textField =
          tester.widget<TextFormField>(find.byType(TextFormField));
      expect(
        textField.controller?.text,
        equals('https://api.example.com'),
      );
    });

    testWidgets('clears error when probing new server', (tester) async {
      final mockClient = _createMockClient(body: testProvidersJson);

      await tester.pumpWidget(
        createLoginScreenApp(
          overrides: [
            httpClientProvider.overrideWithValue(mockClient),
          ],
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byType(TextFormField),
        'https://new-server.com',
      );
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      // Should show providers, not the old error
      expect(find.text('Sign in with'), findsOneWidget);
    });
  });

  group('LoginScreen - Login Flow', () {
    testWidgets('tapping provider initiates login', (tester) async {
      final testNotifier = TestAppStateNotifier(
        const AppStateNeedsAuth(
          serverId: 'https://api.example.com',
          providers: testProviders,
        ),
      );

      // Mock orchestrator returns redirect so state stays at Authenticating
      final mockOrchestrator = MockAuthOrchestrator(
        loginResult: const LoginAttemptRedirect(),
      );

      await tester.pumpWidget(
        createLoginScreenApp(
          overrides: [
            appStateProvider.overrideWith(() => testNotifier),
            authOrchestratorProvider.overrideWithValue(mockOrchestrator),
          ],
        ),
      );
      await tester.pumpAndSettle();

      // Verify providers are shown
      expect(find.text('Sign in with'), findsOneWidget);
      expect(find.text('Keycloak'), findsOneWidget);

      // Tap the provider button
      await tester.tap(find.text('Keycloak'));
      // Use pump() because LinearProgressIndicator animates indefinitely
      await tester.pump();
      await tester.pump();

      // Verify state transitioned to Authenticating
      expect(testNotifier.state, isA<AppStateAuthenticating>());
    });

    testWidgets('shows progress indicator during login', (tester) async {
      await tester.pumpWidget(
        createLoginScreenApp(
          overrides: [
            appStateProvider.overrideWith(
              () => TestAppStateNotifier(
                const AppStateAuthenticating(
                  serverId: 'https://api.example.com',
                  providers: testProviders,
                ),
              ),
            ),
          ],
        ),
      );
      // Use pump() because LinearProgressIndicator animates indefinitely
      await tester.pump();
      await tester.pump();

      // Should show linear progress indicator
      expect(find.byType(LinearProgressIndicator), findsOneWidget);
    });

    testWidgets('disables inputs during login', (tester) async {
      await tester.pumpWidget(
        createLoginScreenApp(
          overrides: [
            appStateProvider.overrideWith(
              () => TestAppStateNotifier(
                const AppStateAuthenticating(
                  serverId: 'https://api.example.com',
                  providers: testProviders,
                ),
              ),
            ),
          ],
        ),
      );
      // Use pump() because of infinite animations
      await tester.pump();
      await tester.pump();

      // Text field should be disabled
      final textField =
          tester.widget<TextFormField>(find.byType(TextFormField));
      expect(textField.enabled, isFalse);

      // Connect button should be disabled
      final connectButton =
          tester.widget<FilledButton>(find.byType(FilledButton));
      expect(connectButton.onPressed, isNull);
    });

    testWidgets('preserves providers on login failure for retry',
        (tester) async {
      final mockOrchestrator = MockAuthOrchestrator(
        probeResult: const ProbeSuccess(providers: testProviders),
        loginResult: const LoginAttemptFailure(message: 'Auth failed'),
      );

      await tester.pumpWidget(
        createLoginScreenApp(
          overrides: [
            authOrchestratorProvider.overrideWithValue(mockOrchestrator),
          ],
        ),
      );
      await tester.pumpAndSettle();

      // First, probe the server to get providers
      await tester.tap(find.text('Connect'));
      await tester.pumpAndSettle();

      // Verify providers are shown
      expect(find.text('Keycloak'), findsOneWidget);

      // Tap the provider button to trigger login (which fails)
      await tester.tap(find.text('Keycloak'));
      await tester.pumpAndSettle();

      // Error should be shown AND providers should still be visible for retry
      expect(find.text('Auth failed'), findsOneWidget);
      expect(find.text('Keycloak'), findsOneWidget);
      expect(find.text('Sign in with'), findsOneWidget);
    });
  });

  group('LoginScreen - Probing State', () {
    testWidgets('shows probing state correctly', (tester) async {
      await tester.pumpWidget(
        createLoginScreenApp(
          overrides: [
            appStateProvider.overrideWith(
              () => TestAppStateNotifier(
                const AppStateProbing(serverId: 'https://api.example.com'),
              ),
            ),
          ],
        ),
      );
      // Use pump() because CircularProgressIndicator animates indefinitely
      await tester.pump();
      await tester.pump();

      // Should show loading indicator
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      // Server URL should be pre-filled
      final textField =
          tester.widget<TextFormField>(find.byType(TextFormField));
      expect(
        textField.controller?.text,
        equals('https://api.example.com'),
      );

      // Text field should be disabled
      expect(textField.enabled, isFalse);
    });
  });
}
