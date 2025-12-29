import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/network/connection_manager.dart';
import 'package:soliplex/core/network/connection_registry.dart';
import 'package:soliplex/core/network/network_transport_layer.dart';
import 'package:soliplex/core/utils/url_builder.dart';

/// Information about a thread from the API.
class ThreadInfo {
  ThreadInfo({
    required this.threadId,
    required this.createdAt,
    this.title,
    this.updatedAt,
    this.messageCount = 0,
  });

  factory ThreadInfo.fromJson(Map<String, dynamic> json) {
    return ThreadInfo(
      threadId: json['thread_id'] as String,
      title: json['title'] as String?,
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'] as String)
          : DateTime.now(),
      updatedAt: json['updated_at'] != null
          ? DateTime.parse(json['updated_at'] as String)
          : null,
      messageCount: json['message_count'] as int? ?? 0,
    );
  }
  final String threadId;
  final String? title;
  final DateTime createdAt;
  final DateTime? updatedAt;
  final int messageCount;
}

/// State for thread history.
class ThreadHistoryState {
  const ThreadHistoryState({
    this.threads = const [],
    this.isLoading = false,
    this.error,
    this.selectedThreadId,
  });
  final List<ThreadInfo> threads;
  final bool isLoading;
  final String? error;
  final String? selectedThreadId;

  ThreadHistoryState copyWith({
    List<ThreadInfo>? threads,
    bool? isLoading,
    String? error,
    String? selectedThreadId,
    bool clearError = false,
    bool clearSelection = false,
  }) {
    return ThreadHistoryState(
      threads: threads ?? this.threads,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
      selectedThreadId: clearSelection
          ? null
          : (selectedThreadId ?? this.selectedThreadId),
    );
  }
}

/// Notifier for managing thread history state.
class ThreadHistoryNotifier extends StateNotifier<ThreadHistoryState> {
  ThreadHistoryNotifier({
    required this.baseUrl,
    required this.roomId,
    required ConnectionManager connectionManager,
    NetworkTransportLayer? transportLayer,
  }) : _connectionManager = connectionManager,
       _transportLayer = transportLayer,
       _urlBuilder = UrlBuilder(baseUrl),
       super(const ThreadHistoryState());
  final String baseUrl;
  final String roomId;
  final ConnectionManager _connectionManager;
  final NetworkTransportLayer? _transportLayer;
  final UrlBuilder _urlBuilder;

  /// Fetch threads from the API.
  Future<void> fetchThreads() async {
    if (_transportLayer == null) {
      debugPrint('ThreadHistory: No transport layer available');
      state = state.copyWith(
        isLoading: false,
        error: 'No transport layer configured',
      );
      return;
    }

    state = state.copyWith(isLoading: true, clearError: true);

    try {
      // Use roomThreads() - threads are listed at /rooms/{roomId}/agui
      final uri = _urlBuilder.roomThreads(roomId);
      debugPrint('ThreadHistory: Fetching threads from $uri');

      final response = await _transportLayer.get(uri);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);

        // API returns {"threads": [...]} where threads is a list of thread
        // objects
        final threadsList = data['threads'] as List<dynamic>? ?? [];

        final threads = threadsList.map((threadData) {
          final t = threadData as Map<String, dynamic>;
          return ThreadInfo(
            threadId: t['thread_id'] as String,
            title: t['title'] as String?,
            createdAt: t['created'] != null
                ? DateTime.parse(t['created'] as String)
                : DateTime.now(),
            updatedAt: t['updated'] != null
                ? DateTime.parse(t['updated'] as String)
                : null,
            messageCount: (t['runs'] as List?)?.length ?? 0,
          );
        }).toList();

        // Sort by creation date, newest first
        threads.sort((a, b) => b.createdAt.compareTo(a.createdAt));

        debugPrint('ThreadHistory: Fetched ${threads.length} threads');
        state = state.copyWith(threads: threads, isLoading: false);
      } else {
        debugPrint(
          'ThreadHistory: Error ${response.statusCode}: ${response.body}',
        );
        state = state.copyWith(
          isLoading: false,
          error: 'Failed to fetch threads: ${response.statusCode}',
        );
      }
    } on Object catch (e) {
      debugPrint('ThreadHistory: Exception: $e');
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  /// Delete a thread.
  Future<void> deleteThread(String threadId) async {
    try {
      final uri = _urlBuilder.thread(roomId, threadId);
      debugPrint('ThreadHistory: Deleting thread $threadId at $uri');

      // Use ConnectionManager to perform the delete
      final response = await _connectionManager.delete(uri);

      if (response.statusCode == 200 || response.statusCode == 204) {
        debugPrint('ThreadHistory: Thread deleted successfully');

        // Handle session cleanup if this was the active thread
        final activeInfo = _connectionManager.getConnectionInfo(roomId);
        if (activeInfo?.threadId == threadId) {
          debugPrint(
            'ThreadHistory: Deleted active thread, clearing session',
          );
          _connectionManager.clearMessages(roomId);
          _connectionManager.disposeSession(roomId);
        }

        // Remove from local list
        final updatedThreads =
            state.threads.where((t) => t.threadId != threadId).toList();

        // If the deleted thread was selected, clear selection
        final shouldClearSelection = state.selectedThreadId == threadId;

        state = state.copyWith(
          threads: updatedThreads,
          clearSelection: shouldClearSelection,
        );
      } else {
        debugPrint(
          'ThreadHistory: Failed to delete thread: ${response.statusCode}',
        );
      }
    } on Object catch (e) {
      debugPrint('ThreadHistory: Exception deleting thread: $e');
    }
  }

  /// Select a thread.
  void selectThread(String? threadId) {
    if (threadId == null) {
      state = state.copyWith(clearSelection: true);
    } else {
      state = state.copyWith(selectedThreadId: threadId);
    }
  }

  /// Clear the thread list.
  void clear() {
    state = const ThreadHistoryState();
  }
}

/// Provider for thread history, scoped by server and room.
///
/// Uses NetworkTransportLayer from ConnectionRegistry for:
/// - Automatic auth header injection
/// - 401 retry with header refresh
/// - Network Inspector visibility
final StateNotifierProviderFamily<
  ThreadHistoryNotifier,
  ThreadHistoryState,
  ({String roomId, String serverId})
>
threadHistoryProvider =
    StateNotifierProvider.family<
      ThreadHistoryNotifier,
      ThreadHistoryState,
      ({String serverId, String roomId})
    >((ref, params) {
      final registry = ref.read(connectionRegistryProvider);
      final serverState = registry.getServerState(params.serverId);
      final connectionManager = ref.read(connectionManagerProvider);

      return ThreadHistoryNotifier(
        baseUrl: serverState?.baseUrl ?? '',
        roomId: params.roomId,
        connectionManager: connectionManager,
        transportLayer: serverState?.transportLayer,
      );
    });
