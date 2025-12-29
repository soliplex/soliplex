import 'package:flutter/material.dart';

/// Configuration for AppShell's Scaffold.
///
/// Screens provide this to configure the shell without having their own
/// Scaffold. This avoids nested Scaffold issues where inner Scaffolds
/// can't access the shell's drawers.
class ShellConfig {
  const ShellConfig({
    this.title,
    this.leading,
    this.actions = const [],
    this.drawer,
  });

  /// The primary widget displayed in the AppBar.
  final Widget? title;

  /// Widget to display before the [title].
  final Widget? leading;

  /// Widgets to display after the [title].
  /// The HTTP inspector button is automatically appended.
  final List<Widget> actions;

  /// Optional drawer for mobile navigation (e.g., thread list).
  /// Shown as leading drawer, separate from the HTTP inspector endDrawer.
  final Widget? drawer;
}
