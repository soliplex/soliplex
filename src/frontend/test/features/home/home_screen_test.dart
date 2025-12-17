import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/features/home/home_screen.dart';

import '../../helpers/test_helpers.dart';

void main() {
  group('HomeScreen', () {
    testWidgets('displays welcome message', (tester) async {
      await tester.pumpWidget(
        createTestApp(home: const HomeScreen()),
      );

      expect(find.text('Welcome to Soliplex'), findsOneWidget);
      expect(find.text('AI-powered RAG system'), findsOneWidget);
    });

    testWidgets('has button to navigate to rooms', (tester) async {
      await tester.pumpWidget(
        createTestApp(home: const HomeScreen()),
      );

      expect(find.text('Go to Rooms'), findsOneWidget);
    });
  });
}
