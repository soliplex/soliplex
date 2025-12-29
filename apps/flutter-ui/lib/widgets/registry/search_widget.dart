import 'dart:async';

import 'package:flutter/material.dart';

/// Interactive search widget for selecting items from a list.
///
/// Data schema:
/// {
///   "placeholder": "Search...",
///   "multi_select": true,
///   "items": [{"id": "1", "title": "Name", "subtitle": "Description"}],
///   "min_chars": 1,
/// }
///
/// Events emitted:
/// - "submit": {selected: [{id, title, subtitle}, ...]}
/// - "cancel": {}
class SearchWidget extends StatefulWidget {
  const SearchWidget({required this.data, super.key, this.onEvent});
  final Map<String, dynamic> data;
  final void Function(String eventName, Map<String, dynamic> payload)? onEvent;

  @override
  State<SearchWidget> createState() => _SearchWidgetState();
}

class _SearchWidgetState extends State<SearchWidget> {
  final _searchController = TextEditingController();
  final Set<String> _selectedIds = {};
  String _query = '';
  Timer? _debounce;

  List<Map<String, dynamic>> get _items {
    final items = widget.data['items'];
    if (items is List) {
      return items.cast<Map<String, dynamic>>();
    }
    return [];
  }

  bool _multiSelect(Map<String, dynamic> args) =>
      args['multi_select'] as bool? ?? false;
  String _placeholder(Map<String, dynamic> args) =>
      args['placeholder'] as String? ?? 'Search...';
  int _minChars(Map<String, dynamic> args) => args['min_chars'] as int? ?? 3;
  String? get _toolCallId => widget.data['_toolCallId'] as String?;

  List<Map<String, dynamic>> get _filteredItems {
    if (_query.length < _minChars(widget.data)) {
      return _items;
    }
    final queryLower = _query.toLowerCase();
    return _items.where((item) {
      final title = (item['title'] ?? '').toString().toLowerCase();
      final subtitle = (item['subtitle'] ?? '').toString().toLowerCase();
      return title.contains(queryLower) || subtitle.contains(queryLower);
    }).toList();
  }

  List<Map<String, dynamic>> get _selectedItems {
    return _items.where((item) => _selectedIds.contains(item['id'])).toList();
  }

  @override
  void dispose() {
    _searchController.dispose();
    _debounce?.cancel();
    super.dispose();
  }

  void _onSearchChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 200), () {
      setState(() => _query = value);
    });
  }

  void _toggleSelection(Map<String, dynamic> item) {
    final id = item['id'] as String;
    setState(() {
      if (_multiSelect(widget.data)) {
        if (_selectedIds.contains(id)) {
          _selectedIds.remove(id);
        } else {
          _selectedIds.add(id);
        }
      } else {
        _selectedIds.clear();
        _selectedIds.add(id);
      }
    });
  }

  void _handleSubmit() {
    widget.onEvent?.call('submit', {
      'selected': _selectedItems,
      if (_toolCallId != null) '_toolCallId': _toolCallId,
    });
  }

  void _handleCancel() {
    widget.onEvent?.call('cancel', {
      if (_toolCallId != null) '_toolCallId': _toolCallId,
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.all(8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Header
            Row(
              children: [
                Icon(Icons.search, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'Search & Select',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const Spacer(),
                if (_selectedIds.isNotEmpty)
                  Chip(
                    label: Text('${_selectedIds.length} selected'),
                    backgroundColor: theme.colorScheme.primaryContainer,
                  ),
              ],
            ),
            const SizedBox(height: 12),

            // Search input
            TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: _placeholder(widget.data),
                prefixIcon: const Icon(Icons.search),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
                filled: true,
                suffixIcon: _query.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchController.clear();
                          setState(() => _query = '');
                        },
                      )
                    : null,
              ),
              onChanged: _onSearchChanged,
            ),
            const SizedBox(height: 12),

            // Results list
            Container(
              constraints: const BoxConstraints(maxHeight: 250),
              decoration: BoxDecoration(
                border: Border.all(color: theme.dividerColor),
                borderRadius: BorderRadius.circular(8),
              ),
              child: _filteredItems.isEmpty
                  ? Center(
                      child: Padding(
                        padding: const EdgeInsets.all(24),
                        child: Text(
                          _query.isEmpty
                              ? 'Type to search'
                              : 'No results found',
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: theme.hintColor,
                          ),
                        ),
                      ),
                    )
                  : ListView.separated(
                      shrinkWrap: true,
                      itemCount: _filteredItems.length,
                      separatorBuilder: (_, _) => const Divider(height: 1),
                      itemBuilder: (context, index) {
                        final item = _filteredItems[index];
                        final id = item['id'] as String;
                        final isSelected = _selectedIds.contains(id);

                        return ListTile(
                          leading: _multiSelect(widget.data)
                              ? Checkbox(
                                  value: isSelected,
                                  onChanged: (_) => _toggleSelection(item),
                                )
                              : Icon(
                                  isSelected
                                      ? Icons.radio_button_checked
                                      : Icons.radio_button_unchecked,
                                  color: isSelected
                                      ? theme.colorScheme.primary
                                      : null,
                                ),
                          title: Text('${item['title'] ?? ''}'),
                          subtitle: item['subtitle'] != null
                              ? Text('${item['subtitle']}')
                              : null,
                          selected: isSelected,
                          selectedTileColor: theme.colorScheme.primaryContainer
                              .withValues(alpha: 0.3),
                          onTap: () => _toggleSelection(item),
                        );
                      },
                    ),
            ),

            // Selected items chips
            if (_selectedIds.isNotEmpty) ...[
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 4,
                children: _selectedItems.map((item) {
                  return Chip(
                    label: Text('${item['title'] ?? item['id']}'),
                    deleteIcon: const Icon(Icons.close, size: 18),
                    onDeleted: () => _toggleSelection(item),
                  );
                }).toList(),
              ),
            ],

            const SizedBox(height: 16),

            // Action buttons
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: _handleCancel,
                  child: const Text('Cancel'),
                ),
                const SizedBox(width: 8),
                FilledButton.icon(
                  onPressed: _selectedIds.isEmpty ? null : _handleSubmit,
                  icon: const Icon(Icons.check),
                  label: Text(
                    _selectedIds.isEmpty
                        ? 'Select items'
                        : 'Submit (${_selectedIds.length})',
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
