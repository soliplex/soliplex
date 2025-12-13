import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Key for storing pinned items in SharedPreferences.
const _pinnedItemsKey = 'soliplex_pinned_items';

/// Provider for SharedPreferences instance.
final _sharedPrefsProvider = FutureProvider<SharedPreferences>((ref) {
  return SharedPreferences.getInstance();
});

/// Provider for pinned items.
final pinnedItemsProvider = StateNotifierProvider<PinnedItemsNotifier, List<PinnedItem>>((ref) {
  final prefsAsync = ref.watch(_sharedPrefsProvider);
  return PinnedItemsNotifier(prefsAsync.valueOrNull);
});

/// Represents a pinned item in the permanent canvas.
class PinnedItem {
  const PinnedItem({
    required this.id,
    required this.title,
    required this.content,
    required this.pinnedAt,
    this.roomId,
    this.threadId,
    this.type = 'text',
  });

  factory PinnedItem.fromJson(Map<String, dynamic> json) {
    return PinnedItem(
      id: json['id'] as String,
      title: json['title'] as String,
      content: json['content'] as String,
      pinnedAt: DateTime.parse(json['pinnedAt'] as String),
      roomId: json['roomId'] as String?,
      threadId: json['threadId'] as String?,
      type: json['type'] as String? ?? 'text',
    );
  }

  final String id;
  final String title;
  final String content;
  final DateTime pinnedAt;
  final String? roomId;
  final String? threadId;
  final String type;

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'content': content,
      'pinnedAt': pinnedAt.toIso8601String(),
      'roomId': roomId,
      'threadId': threadId,
      'type': type,
    };
  }

  PinnedItem copyWith({
    String? id,
    String? title,
    String? content,
    DateTime? pinnedAt,
    String? roomId,
    String? threadId,
    String? type,
  }) {
    return PinnedItem(
      id: id ?? this.id,
      title: title ?? this.title,
      content: content ?? this.content,
      pinnedAt: pinnedAt ?? this.pinnedAt,
      roomId: roomId ?? this.roomId,
      threadId: threadId ?? this.threadId,
      type: type ?? this.type,
    );
  }
}

/// Notifier for managing pinned items with persistence.
class PinnedItemsNotifier extends StateNotifier<List<PinnedItem>> {
  PinnedItemsNotifier(this._prefs) : super([]) {
    _loadItems();
  }

  final SharedPreferences? _prefs;

  void _loadItems() {
    if (_prefs == null) return;
    final json = _prefs.getString(_pinnedItemsKey);
    if (json != null) {
      try {
        final list = jsonDecode(json) as List<dynamic>;
        state = list
            .map((e) => PinnedItem.fromJson(e as Map<String, dynamic>))
            .toList();
      } catch (_) {
        state = [];
      }
    }
  }

  Future<void> _saveItems() async {
    if (_prefs == null) return;
    final json = jsonEncode(state.map((e) => e.toJson()).toList());
    await _prefs.setString(_pinnedItemsKey, json);
  }

  void addItem(PinnedItem item) {
    state = [...state, item];
    _saveItems();
  }

  void removeItem(String id) {
    state = state.where((item) => item.id != id).toList();
    _saveItems();
  }

  void updateItem(String id, PinnedItem updatedItem) {
    state = state.map((item) => item.id == id ? updatedItem : item).toList();
    _saveItems();
  }

  void reorder(int oldIndex, int newIndex) {
    if (oldIndex < newIndex) {
      newIndex -= 1;
    }
    final items = [...state];
    final item = items.removeAt(oldIndex);
    items.insert(newIndex, item);
    state = items;
    _saveItems();
  }
}

/// Widget displaying user-pinned items that persist across app restarts.
class PermanentCanvasWidget extends ConsumerWidget {
  const PermanentCanvasWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pinnedItems = ref.watch(pinnedItemsProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _CanvasHeader(
          itemCount: pinnedItems.length,
          onAdd: () => _showAddDialog(context, ref),
        ),
        Expanded(
          child: pinnedItems.isEmpty
              ? const _EmptyPermanentCanvas()
              : _PinnedItemsList(items: pinnedItems),
        ),
      ],
    );
  }

  Future<void> _showAddDialog(BuildContext context, WidgetRef ref) async {
    final titleController = TextEditingController();
    final contentController = TextEditingController();

    final result = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add Pinned Item'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: titleController,
              decoration: const InputDecoration(
                labelText: 'Title',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: contentController,
              decoration: const InputDecoration(
                labelText: 'Content',
                border: OutlineInputBorder(),
              ),
              maxLines: 4,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Add'),
          ),
        ],
      ),
    );

    if (result == true && titleController.text.isNotEmpty) {
      final item = PinnedItem(
        id: 'pin_${DateTime.now().millisecondsSinceEpoch}',
        title: titleController.text,
        content: contentController.text,
        pinnedAt: DateTime.now(),
      );
      ref.read(pinnedItemsProvider.notifier).addItem(item);
    }

    // Dispose controllers after the frame to avoid issues with ongoing animations
    WidgetsBinding.instance.addPostFrameCallback((_) {
      titleController.dispose();
      contentController.dispose();
    });
  }
}

class _CanvasHeader extends StatelessWidget {
  const _CanvasHeader({
    required this.itemCount,
    required this.onAdd,
  });

  final int itemCount;
  final VoidCallback onAdd;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).dividerColor,
          ),
        ),
      ),
      child: Row(
        children: [
          const Icon(Icons.push_pin, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Pinned ($itemCount)',
              style: const TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 16,
              ),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'Add Item',
            onPressed: onAdd,
            iconSize: 20,
            constraints: const BoxConstraints(
              minWidth: 32,
              minHeight: 32,
            ),
          ),
        ],
      ),
    );
  }
}

class _PinnedItemsList extends ConsumerWidget {
  const _PinnedItemsList({required this.items});

  final List<PinnedItem> items;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ReorderableListView.builder(
      padding: const EdgeInsets.all(8),
      itemCount: items.length,
      onReorder: (oldIndex, newIndex) {
        ref.read(pinnedItemsProvider.notifier).reorder(oldIndex, newIndex);
      },
      itemBuilder: (context, index) {
        final item = items[index];
        return _PinnedItemCard(
          key: ValueKey(item.id),
          item: item,
          onDelete: () {
            ref.read(pinnedItemsProvider.notifier).removeItem(item.id);
          },
        );
      },
    );
  }
}

class _PinnedItemCard extends StatelessWidget {
  const _PinnedItemCard({
    required this.item,
    required this.onDelete,
    super.key,
  });

  final PinnedItem item;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.push_pin, size: 14),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    item.title,
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.delete_outline, size: 18),
                  onPressed: onDelete,
                  tooltip: 'Delete',
                  constraints: const BoxConstraints(
                    minWidth: 28,
                    minHeight: 28,
                  ),
                  padding: EdgeInsets.zero,
                  iconSize: 18,
                ),
              ],
            ),
            if (item.content.isNotEmpty) ...[
              const SizedBox(height: 8),
              SelectableText(
                item.content,
                style: theme.textTheme.bodyMedium,
                maxLines: 5,
              ),
            ],
            const SizedBox(height: 8),
            Row(
              children: [
                Icon(
                  Icons.access_time,
                  size: 12,
                  color: theme.colorScheme.outline,
                ),
                const SizedBox(width: 4),
                Text(
                  _formatDate(item.pinnedAt),
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.outline,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final diff = now.difference(date);

    if (diff.inDays == 0) {
      return 'Today at ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
    } else if (diff.inDays == 1) {
      return 'Yesterday';
    } else if (diff.inDays < 7) {
      return '${diff.inDays} days ago';
    } else {
      return '${date.month}/${date.day}/${date.year}';
    }
  }
}

class _EmptyPermanentCanvas extends StatelessWidget {
  const _EmptyPermanentCanvas();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.push_pin_outlined,
            size: 64,
            color: theme.colorScheme.outline,
          ),
          const SizedBox(height: 16),
          Text(
            'No pinned items',
            style: TextStyle(
              fontSize: 16,
              color: theme.colorScheme.outline,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Pin items to keep them across sessions',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.outline,
            ),
          ),
        ],
      ),
    );
  }
}
