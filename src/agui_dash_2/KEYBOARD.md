# Keyboard Shortcuts System

Documentation for the extensible keyboard shortcut system in AG-UI Dashboard.

## Overview

The keyboard shortcut system provides:
- Centralized shortcut registration and management
- Cross-platform support (macOS, Windows, Linux, Web)
- Extensible architecture for adding new shortcuts
- Auto-generated help dialog showing all shortcuts

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              KeyboardShortcutService                    │
│  (Singleton registry)                                   │
│  ├── register(ShortcutDefinition)                      │
│  ├── getAll() → List<ShortcutDefinition>               │
│  └── getByCategory() → Map<Category, List>             │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                 ShortcutDefinition                      │
│  ├── id, label, description                            │
│  ├── category (general, navigation, view, editing)     │
│  ├── trigger (LogicalKeyboardKey)                      │
│  ├── modifiers (control, shift, alt)                   │
│  ├── getActivator(isMac) → SingleActivator             │
│  └── getDisplayKeys(isMac) → String                    │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│             KeyboardShortcutsWidget                     │
│  (Wraps app content)                                    │
│  ├── Builds Shortcuts map from registry                │
│  ├── Routes actions to ShortcutActions handlers        │
│  └── Platform-aware key display                        │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│            KeyboardShortcutsHelpDialog                  │
│  ├── Groups shortcuts by category                      │
│  └── Shows platform-appropriate key symbols            │
└─────────────────────────────────────────────────────────┘
```

## Files

| File | Purpose |
|------|---------|
| `lib/core/services/keyboard_shortcut_service.dart` | Registry, definitions, categories |
| `lib/core/services/shortcut_actions.dart` | Action handlers |
| `lib/features/keyboard/keyboard_shortcuts_widget.dart` | Flutter Shortcuts/Actions wrapper |
| `lib/features/keyboard/keyboard_shortcuts_help_dialog.dart` | Help modal UI |

## Cross-Platform Design

### The Browser Problem

**Cmd/Ctrl shortcuts don't work on web** because browsers intercept them:
- `Cmd+1-9` → Browser tab switching
- `Cmd+F` → Browser find
- `Cmd+[/]` → Browser back/forward
- `Cmd+/` → Various browser/extension uses

### Solution: Alt/Option-Based Shortcuts

We use **Alt (Option on Mac)** as the primary modifier because:
1. Browsers rarely capture Alt-based shortcuts
2. Works consistently across all platforms including web
3. Single shortcut set works everywhere (no platform-specific variants needed)

### Current Shortcuts

| Category | Action | Shortcut | Mac Display |
|----------|--------|----------|-------------|
| **General** |
| | Show Help | Alt+/ | ⌥/ |
| **Navigation** |
| | Room 1-9 | Alt+1-9 | ⌥1-9 |
| | Previous Room | Alt+[ | ⌥[ |
| | Next Room | Alt+] | ⌥] |
| **View** |
| | Standard Layout | Alt+Shift+1 | ⌥⇧1 |
| | Canvas Layout | Alt+Shift+2 | ⌥⇧2 |
| | Three Column | Alt+Shift+3 | ⌥⇧3 |
| **Editing** |
| | Search Chat | Alt+F | ⌥F |
| | Paste | Alt+K | ⌥K |

## Platform Detection

Platform detection uses `defaultTargetPlatform` from Flutter foundation (NOT `dart:io Platform`):

```dart
import 'package:flutter/foundation.dart' show defaultTargetPlatform, TargetPlatform;

bool get _isMacOS => defaultTargetPlatform == TargetPlatform.macOS;
```

**Why not `dart:io`?** The `Platform` class from `dart:io` throws `Unsupported operation: Platform._operatingSystem` on web builds.

## Can We Use Different Shortcuts Per Platform?

**Yes**, the architecture supports this. Here's how:

### Option 1: Conditional Registration

Register different shortcuts based on platform:

```dart
void initialize() {
  if (kIsWeb) {
    // Web-safe shortcuts (Alt-based)
    register(ShortcutDefinition(
      id: 'room_1',
      trigger: LogicalKeyboardKey.digit1,
      alt: true,  // Alt+1
      action: 'room_1',
    ));
  } else {
    // Native shortcuts (Cmd/Ctrl-based)
    register(ShortcutDefinition(
      id: 'room_1',
      trigger: LogicalKeyboardKey.digit1,
      control: true,  // Cmd+1 on Mac, Ctrl+1 elsewhere
      action: 'room_1',
    ));
  }
}
```

### Option 2: Multiple Activators Per Action

Extend `ShortcutDefinition` to support multiple key combinations:

```dart
class ShortcutDefinition {
  final LogicalKeyboardKey trigger;
  final LogicalKeyboardKey? altTrigger;  // Alternative trigger
  final bool control;
  final bool alt;
  // ...

  /// Get all activators for this shortcut
  List<SingleActivator> getActivators(bool isMac, bool isWeb) {
    final activators = <SingleActivator>[];

    // Primary activator
    activators.add(SingleActivator(
      trigger,
      control: !isMac && control,
      meta: isMac && control,
      alt: alt,
    ));

    // Add web-safe alternative if on web and using control
    if (isWeb && control) {
      activators.add(SingleActivator(
        trigger,
        alt: true,  // Alt-based fallback
      ));
    }

    return activators;
  }
}
```

### Option 3: Platform-Specific Shortcut Sets

Create separate shortcut configurations:

```dart
abstract class ShortcutConfig {
  List<ShortcutDefinition> get shortcuts;
}

class WebShortcutConfig implements ShortcutConfig {
  @override
  List<ShortcutDefinition> get shortcuts => [
    // All Alt-based
  ];
}

class DesktopShortcutConfig implements ShortcutConfig {
  @override
  List<ShortcutDefinition> get shortcuts => [
    // Cmd/Ctrl-based
  ];
}

// In service initialization:
final config = kIsWeb ? WebShortcutConfig() : DesktopShortcutConfig();
for (final shortcut in config.shortcuts) {
  register(shortcut);
}
```

## Adding New Shortcuts

### Step 1: Register the Shortcut

In `keyboard_shortcut_service.dart`:

```dart
register(const ShortcutDefinition(
  id: 'my_new_action',
  label: 'My New Action',
  description: 'Does something useful',
  category: ShortcutCategory.general,
  trigger: LogicalKeyboardKey.keyM,
  alt: true,  // Alt+M
  action: 'my_new_action',
));
```

### Step 2: Handle the Action

In `shortcut_actions.dart`:

```dart
case 'my_new_action':
  _doMyNewAction(ref, context);
  break;
```

### Step 3: Done!

The shortcut automatically appears in the help dialog with correct platform-specific key display.

## Shortcuts Requiring Local State

Some shortcuts need access to widget-local state (e.g., `TextEditingController`). These are:
- **Excluded** from centralized handling via `excludedActions` parameter
- **Handled locally** in the widget that owns the state
- **Still registered** in the service so they appear in the help dialog

Example: Paste (Alt+K) is handled in `chat_content.dart` because it needs the input controller.

```dart
// In KeyboardShortcutsWidget usage:
KeyboardShortcutsWidget(
  excludedActions: const {'paste'},  // Don't handle centrally
  child: ...,
)

// In chat_content.dart - local handling:
Shortcuts(
  shortcuts: {
    const SingleActivator(LogicalKeyboardKey.keyK, alt: true):
        const _PasteIntent(),
  },
  child: Actions(...),
)
```

## Key Display Symbols

The help dialog uses platform-appropriate symbols:

| Modifier | macOS | Windows/Linux |
|----------|-------|---------------|
| Control/Command | ⌘ | Ctrl |
| Shift | ⇧ | Shift |
| Alt/Option | ⌥ | Alt |

Key combinations are joined differently:
- **macOS**: `⌥⇧1` (no separator)
- **Others**: `Alt+Shift+1` (plus separator)

## Technical Notes

### Why SingleActivator?

We use `SingleActivator` instead of `LogicalKeySet` because:
1. **Better web support** - `LogicalKeySet` has issues with modifier detection on web
2. **Explicit modifier mapping** - Clearly specifies `control` vs `meta` (Cmd)
3. **Simpler mental model** - One key + modifiers, not a set of keys

### Focus Handling

The `KeyboardShortcutsWidget` wraps content in a `Focus` widget with `autofocus: true`. This ensures shortcuts work immediately without requiring a click.

### Shortcut Priority

When text fields have focus, standard text editing shortcuts (Cmd+C, Cmd+V, etc.) take precedence. Our Alt-based shortcuts don't conflict with these.

## Future Enhancements

Potential improvements:
1. **User customization** - Allow users to rebind shortcuts (stored in preferences)
2. **Conflict detection** - Warn when registering duplicate key combinations
3. **Context-sensitive shortcuts** - Different shortcuts based on current view/focus
4. **Shortcut chords** - Multi-key sequences like Vim (e.g., `g g` to go to top)
