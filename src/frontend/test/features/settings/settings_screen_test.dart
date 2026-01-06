import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/core/auth/auth_notifier.dart';
import 'package:soliplex_frontend/core/auth/auth_provider.dart';
import 'package:soliplex_frontend/core/auth/auth_state.dart';
import 'package:soliplex_frontend/core/auth/oidc_issuer.dart';
import 'package:soliplex_frontend/features/settings/settings_screen.dart';

import '../../helpers/test_helpers.dart';

class _MockAuthNotifier extends Notifier<AuthState> implements AuthNotifier {
  @override
  AuthState build() => const Unauthenticated();

  @override
  String? get accessToken => null;

  @override
  Future<void> signIn(OidcIssuer issuer) async {}

  @override
  Future<void> signOut() async {}
}

void main() {
  group('SettingsScreen', () {
    testWidgets('displays app version', (tester) async {
      await tester.pumpWidget(
        createTestApp(home: const SettingsScreen()),
      );

      expect(find.text('App Version'), findsOneWidget);
      expect(find.textContaining('1.0.0'), findsOneWidget);
    });

    testWidgets('displays backend URL', (tester) async {
      await tester.pumpWidget(
        createTestApp(home: const SettingsScreen()),
      );

      expect(find.text('Backend URL'), findsOneWidget);
      expect(find.text('http://localhost:8000'), findsOneWidget);
    });

    testWidgets('shows unauthenticated state', (tester) async {
      await tester.pumpWidget(
        createTestApp(
          home: const SettingsScreen(),
          overrides: [
            authProvider.overrideWith(_MockAuthNotifier.new),
          ],
        ),
      );

      expect(find.text('Authentication'), findsOneWidget);
      expect(find.text('Not signed in'), findsOneWidget);
    });
  });
}
