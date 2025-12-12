import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/activity_status_config.dart';
import '../providers/server_scoped_notifier.dart';

/// State for the activity status indicator.
class ActivityStatusState {
  /// Whether the indicator is visible/active.
  final bool isActive;

  /// Currently displayed message.
  final String? currentMessage;

  /// Current AG-UI event type context.
  final String? currentEventType;

  /// Current tool name context.
  final String? currentToolName;

  /// Index for cycling through messages.
  final int messageIndex;

  const ActivityStatusState({
    this.isActive = false,
    this.currentMessage,
    this.currentEventType,
    this.currentToolName,
    this.messageIndex = 0,
  });

  ActivityStatusState copyWith({
    bool? isActive,
    String? currentMessage,
    String? currentEventType,
    String? currentToolName,
    int? messageIndex,
    bool clearMessage = false,
    bool clearEventType = false,
    bool clearToolName = false,
  }) {
    return ActivityStatusState(
      isActive: isActive ?? this.isActive,
      currentMessage: clearMessage ? null : (currentMessage ?? this.currentMessage),
      currentEventType: clearEventType ? null : (currentEventType ?? this.currentEventType),
      currentToolName: clearToolName ? null : (currentToolName ?? this.currentToolName),
      messageIndex: messageIndex ?? this.messageIndex,
    );
  }
}

/// Notifier that manages activity status state and message cycling.
///
/// Extends [ServerScopedNotifier] to automatically reset when server changes.
/// Also resets when room changes (provider watches selectedRoomProvider).
class ActivityStatusNotifier extends ServerScopedNotifier<ActivityStatusState> {
  final ActivityStatusConfig _config;
  final String? roomId;

  Timer? _initialDelayTimer;
  Timer? _cycleTimer;
  Timer? _injectedMessageTimer;

  ActivityStatusNotifier({ActivityStatusConfig? config, super.serverId, this.roomId})
      : _config = config ?? ActivityStatusConfig.defaultConfig,
        super(const ActivityStatusState());

  /// Start activity indicator (called on RunStarted).
  void startActivity() {
    // Cancel any existing timers
    _cancelTimers();

    // Start initial delay before showing first message
    _initialDelayTimer = Timer(_config.initialDelay, () {
      _showNextMessage();
      _startCycling();
    });
  }

  /// Stop activity indicator (called on RunFinished/Error).
  void stopActivity() {
    _cancelTimers();
    state = const ActivityStatusState();
  }

  /// Handle an AG-UI event to update context.
  void handleEvent(String eventType, {String? toolName}) {
    // Update context
    state = state.copyWith(
      currentEventType: eventType,
      currentToolName: toolName,
      clearToolName: toolName == null,
    );

    // If active, immediately show a message for this context
    if (state.isActive) {
      _showNextMessage(resetIndex: true);
    }
  }

  /// Inject a custom message (client API).
  ///
  /// The message will be shown for [duration] before returning to cycling.
  void injectMessage(String message, {Duration? duration}) {
    // Cancel injected message timer if exists
    _injectedMessageTimer?.cancel();

    state = state.copyWith(
      isActive: true,
      currentMessage: message,
    );

    // If duration specified, return to normal cycling after
    if (duration != null) {
      _injectedMessageTimer = Timer(duration, () {
        if (state.isActive) {
          _showNextMessage();
        }
      });
    }
  }

  /// Show the next message based on current context.
  void _showNextMessage({bool resetIndex = false}) {
    final messages = _config.getMessages(
      eventType: state.currentEventType,
      toolName: state.currentToolName,
    );

    if (messages.isEmpty) return;

    final index = resetIndex ? 0 : state.messageIndex % messages.length;
    final message = messages[index];

    state = state.copyWith(
      isActive: true,
      currentMessage: message,
      messageIndex: index + 1,
    );
  }

  /// Start the cycling timer.
  void _startCycling() {
    _cycleTimer?.cancel();
    _cycleTimer = Timer.periodic(_config.cycleInterval, (_) {
      if (state.isActive) {
        _showNextMessage();
      }
    });
  }

  /// Cancel all timers.
  void _cancelTimers() {
    _initialDelayTimer?.cancel();
    _cycleTimer?.cancel();
    _injectedMessageTimer?.cancel();
    _initialDelayTimer = null;
    _cycleTimer = null;
    _injectedMessageTimer = null;
  }

  @override
  void dispose() {
    _cancelTimers();
    super.dispose();
  }
}

/// Provider for activity status configuration.
final activityStatusConfigProvider = StateProvider<ActivityStatusConfig>((ref) {
  return ActivityStatusConfig.defaultConfig;
});

// Note: activityStatusProvider is declared in lib/core/providers/panel_providers.dart
