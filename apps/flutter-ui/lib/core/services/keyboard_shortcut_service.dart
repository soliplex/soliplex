import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Categories for organizing keyboard shortcuts.
enum ShortcutCategory { general, navigation, view, editing }

/// Extension methods for ShortcutCategory.
extension ShortcutCategoryExtension on ShortcutCategory {
  String get displayName {
    switch (this) {
      case ShortcutCategory.general:
        return 'General';
      case ShortcutCategory.navigation:
        return 'Navigation';
      case ShortcutCategory.view:
        return 'View';
      case ShortcutCategory.editing:
        return 'Editing';
    }
  }

  int get sortOrder {
    switch (this) {
      case ShortcutCategory.general:
        return 0;
      case ShortcutCategory.navigation:
        return 1;
      case ShortcutCategory.view:
        return 2;
      case ShortcutCategory.editing:
        return 3;
    }
  }
}

/// Definition of a keyboard shortcut.
class ShortcutDefinition {
  const ShortcutDefinition({
    required this.id,
    required this.label,
    required this.description,
    required this.category,
    required this.trigger,
    required this.action,
    this.control = false,
    this.shift = false,
    this.alt = false,
  });

  /// Unique identifier for the shortcut.
  final String id;

  /// Human-readable label shown in help dialog.
  final String label;

  /// Description of what the shortcut does.
  final String description;

  /// Category for grouping in help dialog.
  final ShortcutCategory category;

  /// The trigger key (e.g., digit1, keyF, slash).
  final LogicalKeyboardKey trigger;

  /// Whether Ctrl/Cmd modifier is required.
  final bool control;

  /// Whether Shift modifier is required.
  final bool shift;

  /// Whether Alt/Option modifier is required.
  final bool alt;

  /// Action identifier passed to handler.
  final String action;

  /// Get SingleActivator for this shortcut (works better on web).
  SingleActivator getActivator({bool isMac = false}) {
    return SingleActivator(
      trigger,
      control: !isMac && control,
      meta: isMac && control, // Cmd on mac, Ctrl elsewhere
      shift: shift,
      alt: alt,
    );
  }

  /// Get display string for the key combination.
  String getDisplayKeys({bool isMac = false}) {
    final parts = <String>[];
    if (control) {
      parts.add(isMac ? '⌘' : 'Ctrl');
    }
    if (shift) {
      parts.add(isMac ? '⇧' : 'Shift');
    }
    if (alt) {
      parts.add(isMac ? '⌥' : 'Alt');
    }
    parts.add(_getKeyLabel(trigger));
    return parts.join(isMac ? '' : '+');
  }

  String _getKeyLabel(LogicalKeyboardKey key) {
    // Digits
    if (key == LogicalKeyboardKey.digit1) return '1';
    if (key == LogicalKeyboardKey.digit2) return '2';
    if (key == LogicalKeyboardKey.digit3) return '3';
    if (key == LogicalKeyboardKey.digit4) return '4';
    if (key == LogicalKeyboardKey.digit5) return '5';
    if (key == LogicalKeyboardKey.digit6) return '6';
    if (key == LogicalKeyboardKey.digit7) return '7';
    if (key == LogicalKeyboardKey.digit8) return '8';
    if (key == LogicalKeyboardKey.digit9) return '9';
    // Letters
    if (key == LogicalKeyboardKey.keyF) return 'F';
    if (key == LogicalKeyboardKey.keyK) return 'K';
    // Special
    if (key == LogicalKeyboardKey.slash) return '/';
    if (key == LogicalKeyboardKey.bracketLeft) return '[';
    if (key == LogicalKeyboardKey.bracketRight) return ']';
    return key.keyLabel;
  }
}

/// Registry service for keyboard shortcuts.
///
/// Provides an extensible system for registering and querying shortcuts.
/// Follows the same pattern as WidgetRegistry for consistency.
class KeyboardShortcutService {
  KeyboardShortcutService._();

  static final KeyboardShortcutService instance = KeyboardShortcutService._();

  final Map<String, ShortcutDefinition> _shortcuts = {};
  bool _initialized = false;

  /// Register a shortcut definition.
  void register(ShortcutDefinition shortcut) {
    _shortcuts[shortcut.id] = shortcut;
  }

  /// Check if a shortcut is registered.
  bool hasShortcut(String id) => _shortcuts.containsKey(id);

  /// Get a shortcut by ID.
  ShortcutDefinition? getShortcut(String id) => _shortcuts[id];

  /// Get all registered shortcuts.
  List<ShortcutDefinition> getAll() => _shortcuts.values.toList();

  /// Get shortcuts grouped by category.
  Map<ShortcutCategory, List<ShortcutDefinition>> getByCategory() {
    final result = <ShortcutCategory, List<ShortcutDefinition>>{};

    for (final shortcut in _shortcuts.values) {
      result.putIfAbsent(shortcut.category, () => []).add(shortcut);
    }

    // Sort categories by their sort order
    final sortedResult = Map.fromEntries(
      result.entries.toList()
        ..sort((a, b) => a.key.sortOrder.compareTo(b.key.sortOrder)),
    );

    return sortedResult;
  }

  /// Initialize with default shortcuts.
  void initialize() {
    if (_initialized) return;
    _initialized = true;

    // General - Alt+/ (browsers don't capture Alt shortcuts)
    register(
      const ShortcutDefinition(
        id: 'show_help',
        label: 'Show Keyboard Shortcuts',
        description: 'Open the keyboard shortcuts help dialog',
        category: ShortcutCategory.general,
        trigger: LogicalKeyboardKey.slash,
        alt: true,
        action: 'show_help',
      ),
    );

    // Navigation - Room switching by number (Alt+1-9)
    final digitKeys = [
      LogicalKeyboardKey.digit1,
      LogicalKeyboardKey.digit2,
      LogicalKeyboardKey.digit3,
      LogicalKeyboardKey.digit4,
      LogicalKeyboardKey.digit5,
      LogicalKeyboardKey.digit6,
      LogicalKeyboardKey.digit7,
      LogicalKeyboardKey.digit8,
      LogicalKeyboardKey.digit9,
    ];

    for (var i = 0; i < 9; i++) {
      register(
        ShortcutDefinition(
          id: 'room_${i + 1}',
          label: 'Switch to Room ${i + 1}',
          description: 'Switch to the ${_ordinal(i + 1)} room',
          category: ShortcutCategory.navigation,
          trigger: digitKeys[i],
          alt: true,
          action: 'room_${i + 1}',
        ),
      );
    }

    // Navigation - Previous/Next room (Alt+[/])
    register(
      const ShortcutDefinition(
        id: 'room_prev',
        label: 'Previous Room',
        description: 'Switch to the previous room',
        category: ShortcutCategory.navigation,
        trigger: LogicalKeyboardKey.bracketLeft,
        alt: true,
        action: 'room_prev',
      ),
    );

    register(
      const ShortcutDefinition(
        id: 'room_next',
        label: 'Next Room',
        description: 'Switch to the next room',
        category: ShortcutCategory.navigation,
        trigger: LogicalKeyboardKey.bracketRight,
        alt: true,
        action: 'room_next',
      ),
    );

    // View - Layout switching (Alt+Shift+1/2/3)
    register(
      const ShortcutDefinition(
        id: 'layout_standard',
        label: 'Standard Layout',
        description: 'Switch to full-screen chat view',
        category: ShortcutCategory.view,
        trigger: LogicalKeyboardKey.digit1,
        alt: true,
        shift: true,
        action: 'layout_standard',
      ),
    );

    register(
      const ShortcutDefinition(
        id: 'layout_canvas',
        label: 'Canvas Layout',
        description: 'Switch to canvas + chat view',
        category: ShortcutCategory.view,
        trigger: LogicalKeyboardKey.digit2,
        alt: true,
        shift: true,
        action: 'layout_canvas',
      ),
    );

    register(
      const ShortcutDefinition(
        id: 'layout_threecol',
        label: 'Three Column Layout',
        description: 'Switch to thread + chat + context view',
        category: ShortcutCategory.view,
        trigger: LogicalKeyboardKey.digit3,
        alt: true,
        shift: true,
        action: 'layout_threecol',
      ),
    );

    // Editing - Paste uses Alt+K, Search uses Alt+F (avoid browser conflicts)
    register(
      const ShortcutDefinition(
        id: 'paste',
        label: 'Paste from Clipboard',
        description: 'Paste content from clipboard into chat',
        category: ShortcutCategory.editing,
        trigger: LogicalKeyboardKey.keyK,
        alt: true,
        action: 'paste',
      ),
    );

    register(
      const ShortcutDefinition(
        id: 'search',
        label: 'Search Chat',
        description: 'Open the chat search bar',
        category: ShortcutCategory.editing,
        trigger: LogicalKeyboardKey.keyF,
        alt: true,
        action: 'search',
      ),
    );
  }

  /// Get ordinal string for a number.
  String _ordinal(int n) {
    if (n >= 11 && n <= 13) return '${n}th';
    switch (n % 10) {
      case 1:
        return '${n}st';
      case 2:
        return '${n}nd';
      case 3:
        return '${n}rd';
      default:
        return '${n}th';
    }
  }
}

/// Riverpod provider for the keyboard shortcut service.
final keyboardShortcutServiceProvider = Provider<KeyboardShortcutService>((
  ref,
) {
  final service = KeyboardShortcutService.instance;
  service.initialize();
  return service;
});
