import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:soliplex_flutter/main.dart';

void main() {
  testWidgets('HomePage displays title and status', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(const ProviderScope(child: SoliplexApp()));

    // Verify app bar title
    expect(find.text('Soliplex'), findsOneWidget);

    // Verify main title
    expect(find.text('Soliplex Flutter'), findsOneWidget);

    // Verify status message
    expect(find.text('Phase 0 Complete - Ready for Phase 1'), findsOneWidget);

    // Verify icon is present
    expect(find.byIcon(Icons.rocket_launch), findsOneWidget);
  });
}
