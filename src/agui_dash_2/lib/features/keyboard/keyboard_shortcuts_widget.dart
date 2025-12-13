import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, TargetPlatform;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/services/keyboard_shortcut_service.dart';
import '../../core/services/shortcut_actions.dart';
import 'keyboard_shortcuts_help_dialog.dart';

/// Check if running on macOS (works on all platforms including web).
bool get _isMacOS => defaultTargetPlatform == TargetPlatform.macOS;

/// Intent for keyboard shortcuts with an action identifier.
class ShortcutIntent extends Intent {
  final String action;
  const ShortcutIntent(this.action);
}

/// Widget that provides global keyboard shortcuts for the app.
///
/// Wraps child content with Flutter's Shortcuts/Actions system.
/// Reads shortcut definitions from KeyboardShortcutService.
///
/// Some shortcuts (like paste) need local state and are excluded from
/// centralized handling. These are still registered in the service for
/// help display but handled by child widgets.
class KeyboardShortcutsWidget extends ConsumerStatefulWidget {
  final Widget child;

  /// Actions to exclude from centralized handling.
  /// These will be handled by child widgets but still shown in help.
  final Set<String> excludedActions;

  const KeyboardShortcutsWidget({
    super.key,
    required this.child,
    this.excludedActions = const {'paste'},
  });

  @override
  ConsumerState<KeyboardShortcutsWidget> createState() =>
      _KeyboardShortcutsWidgetState();
}

class _KeyboardShortcutsWidgetState
    extends ConsumerState<KeyboardShortcutsWidget> {
  @override
  void initState() {
    super.initState();
    // Register the help dialog callback
    ShortcutActions.showHelpDialog = _showHelpDialog;
  }

  @override
  void dispose() {
    ShortcutActions.showHelpDialog = null;
    super.dispose();
  }

  void _showHelpDialog(BuildContext context) {
    KeyboardShortcutsHelpDialog.show(context);
  }

  @override
  Widget build(BuildContext context) {
    final service = ref.watch(keyboardShortcutServiceProvider);
    final isMac = _isMacOS;

    // Build shortcuts map from registry (excluding local-handled ones)
    final shortcuts = <ShortcutActivator, Intent>{};
    for (final shortcut in service.getAll()) {
      // Skip actions that are handled locally by child widgets
      if (widget.excludedActions.contains(shortcut.action)) {
        continue;
      }

      // Use SingleActivator which works better on web
      final activator = shortcut.getActivator(isMac);
      shortcuts[activator] = ShortcutIntent(shortcut.action);
    }

    return Shortcuts(
      shortcuts: shortcuts,
      child: Actions(
        actions: {
          ShortcutIntent: CallbackAction<ShortcutIntent>(
            onInvoke: (intent) {
              ShortcutActions.execute(ref, intent.action, context);
              return null;
            },
          ),
        },
        child: Focus(autofocus: true, child: widget.child),
      ),
    );
  }
}
