import 'package:flutter/foundation.dart'
    show TargetPlatform, defaultTargetPlatform;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/services/keyboard_shortcut_service.dart';

/// Check if running on macOS (works on all platforms including web).
bool get _isMacOS => defaultTargetPlatform == TargetPlatform.macOS;

/// Dialog that displays all available keyboard shortcuts.
///
/// Shows shortcuts grouped by category with platform-appropriate key labels.
class KeyboardShortcutsHelpDialog extends ConsumerWidget {
  const KeyboardShortcutsHelpDialog({super.key});

  /// Show the help dialog.
  static void show({required BuildContext context}) {
    showDialog<void>(
      context: context,
      builder: (_) => const KeyboardShortcutsHelpDialog(),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final service = ref.watch(keyboardShortcutServiceProvider);
    final byCategory = service.getByCategory();
    final isMac = _isMacOS;
    final theme = Theme.of(context);

    return AlertDialog(
      title: Row(
        children: [
          Icon(Icons.keyboard, color: theme.colorScheme.primary),
          const SizedBox(width: 12),
          const Text('Keyboard Shortcuts'),
        ],
      ),
      content: SizedBox(
        width: 450,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: byCategory.entries.map((entry) {
              return _buildCategory(context, entry.key, entry.value, isMac);
            }).toList(),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close'),
        ),
      ],
    );
  }

  Widget _buildCategory(
    BuildContext context,
    ShortcutCategory category,
    List<ShortcutDefinition> shortcuts,
    bool isMac,
  ) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            category.displayName,
            style: theme.textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.bold,
              color: theme.colorScheme.primary,
            ),
          ),
          const SizedBox(height: 8),
          ...shortcuts.map(
            (s) =>
                _buildShortcutRow(context: context, shortcut: s, isMac: isMac),
          ),
        ],
      ),
    );
  }

  Widget _buildShortcutRow({
    required BuildContext context,
    required ShortcutDefinition shortcut,
    required bool isMac,
  }) {
    final theme = Theme.of(context);
    final displayKeys = shortcut.getDisplayKeys(isMac: isMac);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(
            child: Text(shortcut.label, style: theme.textTheme.bodyMedium),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: theme.colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(4),
              border: Border.all(
                color: theme.colorScheme.outline.withAlpha(100),
              ),
            ),
            child: Text(
              displayKeys,
              style: theme.textTheme.bodySmall?.copyWith(
                fontWeight: FontWeight.w600,
                fontFamily: 'monospace',
              ),
            ),
          ),
        ],
      ),
    );
  }
}
