import 'package:flutter/material.dart';
import 'package:soliplex_frontend/features/inspector/http_inspector_panel.dart';
import 'package:soliplex_frontend/shared/widgets/shell_config.dart';

/// Shell widget that wraps all screens with a single Scaffold.
///
/// Provides:
/// - Single Scaffold to avoid nested Scaffold drawer issues
/// - HTTP inspector drawer accessible from all screens
/// - Consistent AppBar with inspector button
class AppShell extends StatelessWidget {
  const AppShell({
    required this.config,
    required this.body,
    super.key,
  });

  /// Configuration for the AppBar and drawers.
  final ShellConfig config;

  /// The screen's body content.
  final Widget body;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: config.leading,
        title: config.title,
        actions: [
          ...config.actions,
          const _InspectorButton(),
        ],
      ),
      drawer: config.drawer != null
          ? Semantics(
              label: 'Navigation drawer',
              child: config.drawer,
            )
          : null,
      endDrawer: Semantics(
        label: 'HTTP traffic inspector panel',
        child: const SizedBox(
          width: 400,
          child: Drawer(child: HttpInspectorPanel()),
        ),
      ),
      floatingActionButton: config.floatingActionButton,
      body: body,
    );
  }
}

/// Button that opens the HTTP inspector drawer.
///
/// Separate widget class ensures build() provides the correct context
/// for Scaffold.of() to find the Scaffold we just built.
class _InspectorButton extends StatelessWidget {
  const _InspectorButton();

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'HTTP traffic inspector',
      child: IconButton(
        icon: const Icon(Icons.bug_report),
        tooltip: 'Open HTTP traffic inspector',
        onPressed: () => Scaffold.of(context).openEndDrawer(),
      ),
    );
  }
}
