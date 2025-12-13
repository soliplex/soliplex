import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Canvas state notifier for managing canvas data.
class CanvasStateNotifier extends StateNotifier<Map<String, dynamic>> {
  CanvasStateNotifier() : super({});

  /// Update the entire canvas state.
  void updateState(Map<String, dynamic> newState) {
    state = newState;
  }

  /// Apply a delta to the canvas state.
  void applyDelta(Map<String, dynamic> delta) {
    state = {...state, ...delta};
  }

  /// Clear the canvas state.
  void clear() {
    state = {};
  }

  /// Get a specific key from the state.
  dynamic getValue(String key) => state[key];

  /// Set a specific key in the state.
  void setValue(String key, dynamic value) {
    state = {...state, key: value};
  }
}

/// Provider for the current canvas state.
///
/// Scoped to the current thread.
final canvasStateProvider = StateNotifierProvider<CanvasStateNotifier, Map<String, dynamic>>((ref) {
  return CanvasStateNotifier();
});

/// Provider for activity state (whether the agent is active).
final isAgentActiveProvider = StateProvider<bool>((ref) {
  return false;
});
