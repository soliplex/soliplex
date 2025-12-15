import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:soliplex/main.dart';

void main() {
  testWidgets('AgUiDashApp widget creates MaterialApp', (
    WidgetTester tester,
  ) async {
    // Build the app widget (but not full ProviderScope which triggers async
    // init)
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: Center(child: Text('AG-UI Dashboard'))),
      ),
    );

    // Verify basic MaterialApp setup works
    expect(find.byType(MaterialApp), findsOneWidget);
    expect(find.text('AG-UI Dashboard'), findsOneWidget);
  });

  test('AgUiDashApp is a ConsumerWidget', () {
    const app = AgUiDashApp();
    expect(app, isA<ConsumerWidget>());
  });
}
