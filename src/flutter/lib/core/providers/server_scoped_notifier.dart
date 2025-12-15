import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/utils/debug_log.dart';

/// Base class for StateNotifiers that must reset when server changes.
///
/// Panel notifiers (chat, canvas, context, activity, etc.) MUST extend this
/// class.
/// This enforces server-scoped lifecycle at the structural level.
///
/// When `currentServerProvider` changes, Riverpod invalidates the provider,
/// disposing the old notifier and creating a new one with the new serverId.
///
/// Usage:
/// ```dart
/// class MyPanelNotifier extends ServerScopedNotifier<MyState> {
///   MyPanelNotifier({super.serverId}) : super(const MyState());
/// }
///
/// // In panel_providers.dart:
/// final myPanelProvider = StateNotifierProvider<MyPanelNotifier,
/// MyState>((ref) {
///   final server = ref.watch(currentServerProvider);
///   return MyPanelNotifier(serverId: server?.id);
/// });
/// ```
abstract class ServerScopedNotifier<State> extends StateNotifier<State> {
  // ignore: matching_super_parameters (auto-documented)
  ServerScopedNotifier(super.initialState, {this.serverId}) {
    DebugLog.service('$runtimeType: Created for server $serverId');
  }

  /// The server ID this notifier was created for.
  /// Null if no server is configured.
  final String? serverId;

  @override
  void dispose() {
    DebugLog.service('$runtimeType: Disposed (server $serverId)');
    super.dispose();
  }
}
