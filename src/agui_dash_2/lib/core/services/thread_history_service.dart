import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../utils/url_builder.dart';

/// Information about a thread from the API.
class ThreadInfo {
  final String threadId;
  final String? title;
  final DateTime createdAt;
  final DateTime? updatedAt;
  final int messageCount;

  ThreadInfo({
    required this.threadId,
    this.title,
    required this.createdAt,
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
}

/// State for thread history.
class ThreadHistoryState {
  final List<ThreadInfo> threads;
  final bool isLoading;
  final String? error;
  final String? selectedThreadId;

  const ThreadHistoryState({
    this.threads = const [],
    this.isLoading = false,
    this.error,
    this.selectedThreadId,
  });

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
  final String baseUrl;
  final String roomId;
  final http.Client _client;
  final UrlBuilder _urlBuilder;

  ThreadHistoryNotifier({
    required this.baseUrl,
    required this.roomId,
    http.Client? client,
  }) : _client = client ?? http.Client(),
       _urlBuilder = UrlBuilder(baseUrl),
       super(const ThreadHistoryState());

  /// Fetch threads from the API.
  Future<void> fetchThreads() async {
    state = state.copyWith(isLoading: true, clearError: true);

    try {
      // Use roomThreads() - threads are listed at /rooms/{roomId}/agui
      final uri = _urlBuilder.roomThreads(roomId);
      debugPrint('ThreadHistory: Fetching threads from $uri');

      final response = await _client.get(
        uri,
        headers: {'Accept': 'application/json'},
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);

        // API returns {"threads": [...]} where threads is a list of thread objects
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
    } catch (e) {
      debugPrint('ThreadHistory: Exception: $e');
      state = state.copyWith(isLoading: false, error: e.toString());
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

/// Provider for thread history, scoped by room.
final threadHistoryProvider =
    StateNotifierProvider.family<
      ThreadHistoryNotifier,
      ThreadHistoryState,
      ({String baseUrl, String roomId})
    >((ref, params) {
      return ThreadHistoryNotifier(
        baseUrl: params.baseUrl,
        roomId: params.roomId,
      );
    });
