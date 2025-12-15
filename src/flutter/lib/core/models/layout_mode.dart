import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Available layout modes for the chat application.
enum LayoutMode {
  /// Full-screen chat (existing default behavior)
  standard,

  /// 2/3 canvas + 1/3 chat for agent-controlled content display
  canvas,

  /// Thread history | Chat | Context pane for comprehensive view
  threecol,
}

/// Extension methods for LayoutMode.
extension LayoutModeExtension on LayoutMode {
  /// Human-readable display name.
  String get displayName {
    switch (this) {
      case LayoutMode.standard:
        return 'Standard';
      case LayoutMode.canvas:
        return 'Canvas';
      case LayoutMode.threecol:
        return 'Three Column';
    }
  }

  /// Icon for the layout mode.
  IconData get icon {
    switch (this) {
      case LayoutMode.standard:
        return Icons.chat;
      case LayoutMode.canvas:
        return Icons.dashboard;
      case LayoutMode.threecol:
        return Icons.view_column;
    }
  }

  /// Short description of the layout.
  String get description {
    switch (this) {
      case LayoutMode.standard:
        return 'Full-screen chat';
      case LayoutMode.canvas:
        return 'Canvas with chat sidebar';
      case LayoutMode.threecol:
        return 'Threads, chat, and context';
    }
  }
}

/// Provider for the current layout mode.
final layoutModeProvider = StateProvider<LayoutMode>((ref) {
  return LayoutMode.standard;
});
