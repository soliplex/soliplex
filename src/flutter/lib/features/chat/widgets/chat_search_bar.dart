import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/services/chat_search_service.dart';

/// Search bar for finding text in chat messages.
class ChatSearchBar extends ConsumerStatefulWidget {
  const ChatSearchBar({
    required this.getMessageText,
    required this.messageIds,
    super.key,
  });

  /// Callback to get message text by ID.
  final String Function(String messageId) getMessageText;

  /// List of all message IDs to search through.
  final List<String> messageIds;

  @override
  ConsumerState<ChatSearchBar> createState() => _ChatSearchBarState();
}

class _ChatSearchBarState extends ConsumerState<ChatSearchBar> {
  final _controller = TextEditingController();
  final _focusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    // Auto-focus when opened
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _focusNode.requestFocus();
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _onSearchChanged(String value) {
    ref
        .read(chatSearchProvider.notifier)
        .search(value, widget.messageIds, widget.getMessageText);
  }

  void _close() {
    ref.read(chatSearchProvider.notifier).closeSearch();
  }

  @override
  Widget build(BuildContext context) {
    final searchState = ref.watch(chatSearchProvider);
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest,
        border: Border(bottom: BorderSide(color: colorScheme.outlineVariant)),
      ),
      child: Row(
        children: [
          // Search icon
          Icon(Icons.search, size: 20, color: colorScheme.onSurfaceVariant),
          const SizedBox(width: 8),

          // Search input
          Expanded(
            child: TextField(
              controller: _controller,
              focusNode: _focusNode,
              decoration: InputDecoration(
                hintText: 'Search in chat...',
                border: InputBorder.none,
                isDense: true,
                contentPadding: EdgeInsets.zero,
                hintStyle: TextStyle(color: colorScheme.onSurfaceVariant),
              ),
              style: TextStyle(color: colorScheme.onSurface),
              onChanged: _onSearchChanged,
              onSubmitted: (_) {
                // Go to next match on Enter
                ref.read(chatSearchProvider.notifier).nextMatch();
              },
            ),
          ),

          // Match count
          if (searchState.query.isNotEmpty) ...[
            Text(
              '${searchState.currentMatchPosition}/${searchState.matchCount}',
              style: TextStyle(
                fontSize: 12,
                color: searchState.hasMatches
                    ? colorScheme.onSurfaceVariant
                    : colorScheme.error,
              ),
            ),
            const SizedBox(width: 8),

            // Previous button
            IconButton(
              icon: const Icon(Icons.keyboard_arrow_up, size: 20),
              onPressed: searchState.hasMatches
                  ? () => ref.read(chatSearchProvider.notifier).previousMatch()
                  : null,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
              tooltip: 'Previous match',
            ),

            // Next button
            IconButton(
              icon: const Icon(Icons.keyboard_arrow_down, size: 20),
              onPressed: searchState.hasMatches
                  ? () => ref.read(chatSearchProvider.notifier).nextMatch()
                  : null,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
              tooltip: 'Next match',
            ),
          ],

          // Close button
          IconButton(
            icon: const Icon(Icons.close, size: 20),
            onPressed: _close,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
            tooltip: 'Close search',
          ),
        ],
      ),
    );
  }
}
