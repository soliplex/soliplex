import 'package:flutter/foundation.dart'
    show TargetPlatform, defaultTargetPlatform;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/services/keyboard_shortcut_service.dart';
import 'package:soliplex/core/services/shortcut_actions.dart';
import 'package:soliplex/features/keyboard/keyboard_shortcuts_help_dialog.dart';

/// Check if running on macOS (works on all platforms including web).
bool get _isMacOS => defaultTargetPlatform == TargetPlatform.macOS;

/// Intent for keyboard shortcuts with an action identifier.
class ShortcutIntent extends Intent {
  const ShortcutIntent(this.action);
  final String action;
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
  const KeyboardShortcutsWidget({
    required this.child,
    super.key,
    this.excludedActions = const {'paste'},
  });
  final Widget child;

  /// Actions to exclude from centralized handling.
  /// These will be handled by child widgets but still shown in help.
  final Set<String> excludedActions;

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
    KeyboardShortcutsHelpDialog.show(context: context);
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
      final activator = shortcut.getActivator(isMac: isMac);
      shortcuts[activator] = ShortcutIntent(shortcut.action);
    }

    return Shortcuts(
      shortcuts: shortcuts,
      child: Actions(
        actions: {
          ShortcutIntent: CallbackAction<ShortcutIntent>(
            onInvoke: (intent) {
              ShortcutActions.execute(
                ref: ref,
                action: intent.action,
                context: context,
              );
              return null;
            },
          ),
        },
        child: Focus(autofocus: true, child: widget.child),
      ),
    );
  }
}
