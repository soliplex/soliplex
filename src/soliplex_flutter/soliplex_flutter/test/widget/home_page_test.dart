import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:soliplex_flutter/app_shell.dart';
import 'package:soliplex_flutter/main.dart';

void main() {
  // Set a larger screen size for AppShell tests
  const testScreenSize = Size(1400, 900);

  testWidgets('AppShell displays app title', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = testScreenSize;
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() => tester.view.resetPhysicalSize());

    await tester.pumpWidget(const ProviderScope(child: SoliplexApp()));

    // Verify app bar title
    expect(find.text('Soliplex'), findsOneWidget);
  });

  testWidgets('AppShell has test page button', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = testScreenSize;
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() => tester.view.resetPhysicalSize());

    await tester.pumpWidget(const ProviderScope(child: SoliplexApp()));

    // Verify test page button exists in app bar
    expect(find.byIcon(Icons.bug_report), findsOneWidget);
  });

  testWidgets('AppShell displays History section', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = testScreenSize;
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() => tester.view.resetPhysicalSize());

    await tester.pumpWidget(const ProviderScope(child: SoliplexApp()));

    // When no room is selected, shows message to select a room
    expect(find.text('Select a room to view threads'), findsOneWidget);
  });

  testWidgets('AppShell displays Canvas tabs', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = testScreenSize;
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() => tester.view.resetPhysicalSize());

    await tester.pumpWidget(const ProviderScope(child: SoliplexApp()));

    // Verify Canvas tabs are visible
    expect(find.text('Current'), findsOneWidget);
    expect(find.text('Pinned'), findsOneWidget);
  });

  testWidgets('AppShell renders without overflow', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = testScreenSize;
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() => tester.view.resetPhysicalSize());

    await tester.pumpWidget(const ProviderScope(child: SoliplexApp()));

    // Just verify it renders without crashing
    expect(find.byType(AppShell), findsOneWidget);
  });

  testWidgets('AppShell navigates to test page', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = testScreenSize;
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() => tester.view.resetPhysicalSize());

    await tester.pumpWidget(const ProviderScope(child: SoliplexApp()));

    // Tap the test page button
    await tester.tap(find.byIcon(Icons.bug_report));
    await tester.pumpAndSettle();

    // Verify we're on the test page
    expect(find.text('Test Page'), findsOneWidget);
    expect(find.text('Server URL'), findsOneWidget);
  });
}
