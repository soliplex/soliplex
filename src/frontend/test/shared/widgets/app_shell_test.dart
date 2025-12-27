import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/shared/widgets/app_shell.dart';
import 'package:soliplex_frontend/shared/widgets/shell_config.dart';

void main() {
  group('AppShell', () {
    testWidgets('renders body content', (tester) async {
      const bodyKey = Key('body');
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: AppShell(
              config: const ShellConfig(),
              body: Container(key: bodyKey, child: const Text('Hello')),
            ),
          ),
        ),
      );

      expect(find.byKey(bodyKey), findsOneWidget);
      expect(find.text('Hello'), findsOneWidget);
    });

    testWidgets('renders title from config', (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(
            home: AppShell(
              config: ShellConfig(title: Text('My Title')),
              body: SizedBox.shrink(),
            ),
          ),
        ),
      );

      expect(find.text('My Title'), findsOneWidget);
    });

    testWidgets('renders leading from config', (tester) async {
      const leadingKey = Key('leading');
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: AppShell(
              config: ShellConfig(
                leading: IconButton(
                  key: leadingKey,
                  icon: const Icon(Icons.arrow_back),
                  onPressed: () {},
                ),
              ),
              body: const SizedBox.shrink(),
            ),
          ),
        ),
      );

      expect(find.byKey(leadingKey), findsOneWidget);
    });

    testWidgets('renders actions from config', (tester) async {
      const actionKey = Key('action');
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: AppShell(
              config: ShellConfig(
                actions: [
                  IconButton(
                    key: actionKey,
                    icon: const Icon(Icons.settings),
                    onPressed: () {},
                  ),
                ],
              ),
              body: const SizedBox.shrink(),
            ),
          ),
        ),
      );

      expect(find.byKey(actionKey), findsOneWidget);
    });

    testWidgets('shows AppBar with inspector button for empty config',
        (tester) async {
      await tester.pumpWidget(
        const ProviderScope(
          child: MaterialApp(
            home: AppShell(
              config: ShellConfig(),
              body: Center(child: Text('Content')),
            ),
          ),
        ),
      );

      expect(find.byType(AppBar), findsOneWidget);
      expect(find.byIcon(Icons.bug_report), findsOneWidget);
    });

    group('HTTP inspector', () {
      testWidgets('shows inspector button in app bar', (tester) async {
        await tester.pumpWidget(
          const ProviderScope(
            child: MaterialApp(
              home: AppShell(
                config: ShellConfig(),
                body: Center(child: Text('Content')),
              ),
            ),
          ),
        );

        expect(find.byIcon(Icons.bug_report), findsOneWidget);
      });

      testWidgets('inspector button has tooltip', (tester) async {
        await tester.pumpWidget(
          const ProviderScope(
            child: MaterialApp(
              home: AppShell(
                config: ShellConfig(),
                body: Center(child: Text('Content')),
              ),
            ),
          ),
        );

        final tooltipFinder = find.byWidgetPredicate(
          (widget) =>
              widget is Tooltip &&
              widget.message == 'Open HTTP traffic inspector',
        );
        expect(tooltipFinder, findsOneWidget);
      });

      testWidgets('inspector button appears after config actions',
          (tester) async {
        await tester.pumpWidget(
          ProviderScope(
            child: MaterialApp(
              home: AppShell(
                config: ShellConfig(
                  actions: [
                    IconButton(
                      key: const Key('action'),
                      icon: const Icon(Icons.settings),
                      onPressed: () {},
                    ),
                  ],
                ),
                body: const SizedBox.shrink(),
              ),
            ),
          ),
        );

        final actionOffset = tester.getCenter(find.byKey(const Key('action')));
        final inspectorOffset = tester.getCenter(find.byIcon(Icons.bug_report));
        expect(inspectorOffset.dx, greaterThan(actionOffset.dx));
      });

      testWidgets('inspector button opens endDrawer', (tester) async {
        await tester.pumpWidget(
          const ProviderScope(
            child: MaterialApp(
              home: AppShell(
                config: ShellConfig(),
                body: Center(child: Text('Content')),
              ),
            ),
          ),
        );

        await tester.tap(find.byIcon(Icons.bug_report));
        await tester.pumpAndSettle();

        expect(find.text('HTTP Inspector'), findsOneWidget);
      });

      testWidgets('endDrawer has Semantics label', (tester) async {
        await tester.pumpWidget(
          const ProviderScope(
            child: MaterialApp(
              home: AppShell(
                config: ShellConfig(),
                body: Center(child: Text('Content')),
              ),
            ),
          ),
        );

        await tester.tap(find.byIcon(Icons.bug_report));
        await tester.pumpAndSettle();

        final semanticsFinder = find.byWidgetPredicate(
          (widget) =>
              widget is Semantics &&
              widget.properties.label == 'HTTP traffic inspector panel',
        );
        expect(semanticsFinder, findsOneWidget);
      });
    });

    group('start drawer', () {
      testWidgets('shows drawer when config provides one', (tester) async {
        const drawerContent = Text('Drawer Content');
        await tester.pumpWidget(
          const ProviderScope(
            child: MaterialApp(
              home: AppShell(
                config: ShellConfig(
                  drawer: Drawer(child: drawerContent),
                ),
                body: SizedBox.shrink(),
              ),
            ),
          ),
        );

        tester.state<ScaffoldState>(find.byType(Scaffold)).openDrawer();
        await tester.pumpAndSettle();

        expect(find.text('Drawer Content'), findsOneWidget);
      });

      testWidgets('drawer is wrapped in Semantics', (tester) async {
        await tester.pumpWidget(
          const ProviderScope(
            child: MaterialApp(
              home: AppShell(
                config: ShellConfig(
                  drawer: Drawer(child: Text('Nav')),
                ),
                body: SizedBox.shrink(),
              ),
            ),
          ),
        );

        tester.state<ScaffoldState>(find.byType(Scaffold)).openDrawer();
        await tester.pumpAndSettle();

        final semanticsFinder = find.byWidgetPredicate(
          (widget) =>
              widget is Semantics &&
              widget.properties.label == 'Navigation drawer',
        );
        expect(semanticsFinder, findsOneWidget);
      });

      testWidgets('no drawer when config does not provide one', (tester) async {
        await tester.pumpWidget(
          const ProviderScope(
            child: MaterialApp(
              home: AppShell(
                config: ShellConfig(),
                body: SizedBox.shrink(),
              ),
            ),
          ),
        );

        final scaffold = tester.widget<Scaffold>(find.byType(Scaffold));
        expect(scaffold.drawer, isNull);
      });
    });
  });

  group('ShellConfig', () {
    test('has sensible defaults', () {
      const config = ShellConfig();
      expect(config.title, isNull);
      expect(config.leading, isNull);
      expect(config.actions, isEmpty);
      expect(config.drawer, isNull);
    });

    test('stores all provided values', () {
      const title = Text('Title');
      final leading = IconButton(
        icon: const Icon(Icons.menu),
        onPressed: () {},
      );
      final actions = [
        IconButton(icon: const Icon(Icons.search), onPressed: () {}),
      ];
      const drawer = Drawer(child: Text('Menu'));

      final config = ShellConfig(
        title: title,
        leading: leading,
        actions: actions,
        drawer: drawer,
      );

      expect(config.title, same(title));
      expect(config.leading, same(leading));
      expect(config.actions, same(actions));
      expect(config.drawer, same(drawer));
    });
  });
}
