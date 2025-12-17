import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/features/settings/settings_screen.dart';

import '../../helpers/test_helpers.dart';

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

    testWidgets('authentication section is disabled', (tester) async {
      await tester.pumpWidget(
        createTestApp(home: const SettingsScreen()),
      );

      expect(find.text('Authentication'), findsOneWidget);
      expect(find.text('Not configured'), findsOneWidget);
      expect(find.text('AM7'), findsOneWidget);
    });
  });
}
