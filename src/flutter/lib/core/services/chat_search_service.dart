import 'package:flutter_riverpod/flutter_riverpod.dart';

/// State for chat search functionality.
class ChatSearchState {
  const ChatSearchState({
    this.isActive = false,
    this.query = '',
    this.matchingMessageIds = const [],
    this.currentMatchIndex = 0,
  });

  /// Whether search is active/visible.
  final bool isActive;

  /// Current search query.
  final String query;

  /// List of message IDs that contain matches.
  final List<String> matchingMessageIds;

  /// Current match index (for navigation).
  final int currentMatchIndex;

  ChatSearchState copyWith({
    bool? isActive,
    String? query,
    List<String>? matchingMessageIds,
    int? currentMatchIndex,
  }) {
    return ChatSearchState(
      isActive: isActive ?? this.isActive,
      query: query ?? this.query,
      matchingMessageIds: matchingMessageIds ?? this.matchingMessageIds,
      currentMatchIndex: currentMatchIndex ?? this.currentMatchIndex,
    );
  }

  /// Total number of matches.
  int get matchCount => matchingMessageIds.length;

  /// Whether there are any matches.
  bool get hasMatches => matchingMessageIds.isNotEmpty;

  /// Current match position (1-indexed for display).
  int get currentMatchPosition => matchCount > 0 ? currentMatchIndex + 1 : 0;
}

/// Notifier for managing chat search state.
class ChatSearchNotifier extends StateNotifier<ChatSearchState> {
  ChatSearchNotifier() : super(const ChatSearchState());

  /// Open search bar.
  void openSearch() {
    state = state.copyWith(isActive: true);
  }

  /// Close search bar and clear state.
  void closeSearch() {
    state = const ChatSearchState();
  }

  /// Update search query and matching messages.
  void search(
    String query,
    List<String> allMessageIds,
    String Function(String) getMessageText,
  ) {
    if (query.isEmpty) {
      state = state.copyWith(
        query: '',
        matchingMessageIds: [],
        currentMatchIndex: 0,
      );
      return;
    }

    final queryLower = query.toLowerCase();
    final matches = <String>[];

    for (final id in allMessageIds) {
      final text = getMessageText(id).toLowerCase();
      if (text.contains(queryLower)) {
        matches.add(id);
      }
    }

    state = state.copyWith(
      query: query,
      matchingMessageIds: matches,
      currentMatchIndex: matches.isNotEmpty ? 0 : 0,
    );
  }

  /// Go to next match.
  void nextMatch() {
    if (!state.hasMatches) return;
    final next = (state.currentMatchIndex + 1) % state.matchCount;
    state = state.copyWith(currentMatchIndex: next);
  }

  /// Go to previous match.
  void previousMatch() {
    if (!state.hasMatches) return;
    final prev =
        (state.currentMatchIndex - 1 + state.matchCount) % state.matchCount;
    state = state.copyWith(currentMatchIndex: prev);
  }
}

/// Provider for chat search.
final chatSearchProvider =
    StateNotifierProvider<ChatSearchNotifier, ChatSearchState>((ref) {
      return ChatSearchNotifier();
    });
