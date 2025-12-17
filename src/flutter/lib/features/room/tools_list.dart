import 'package:flutter/material.dart';

import 'package:soliplex/core/models/room_models.dart';

/// An expandable list of tools available in a room.
///
/// Shows tool names with descriptions, expandable to show parameters.
class ToolsList extends StatefulWidget {
  const ToolsList({
    required this.tools,
    super.key,
    this.initiallyExpanded = false,
    this.title = 'Tools',
    this.icon = Icons.build_outlined,
  });
  final Map<String, RoomTool> tools;
  final bool initiallyExpanded;
  final String title;
  final IconData icon;

  @override
  State<ToolsList> createState() => _ToolsListState();
}

class _ToolsListState extends State<ToolsList> {
  late bool _isExpanded;
  final Set<String> _expandedTools = {};

  @override
  void initState() {
    super.initState();
    _isExpanded = widget.initiallyExpanded;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    if (widget.tools.isEmpty) {
      return const SizedBox.shrink();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header with expand/collapse
        InkWell(
          onTap: () => setState(() => _isExpanded = !_isExpanded),
          borderRadius: BorderRadius.circular(8),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Row(
              children: [
                Icon(
                  widget.icon,
                  size: 18,
                  color: colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Text(
                  widget.title,
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: colorScheme.primaryContainer,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    '${widget.tools.length}',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: colorScheme.onPrimaryContainer,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                const Spacer(),
                Icon(
                  _isExpanded ? Icons.expand_less : Icons.expand_more,
                  size: 20,
                  color: colorScheme.onSurfaceVariant,
                ),
              ],
            ),
          ),
        ),

        // Tool list (when expanded)
        if (_isExpanded)
          Padding(
            padding: const EdgeInsets.only(left: 12),
            child: Column(
              children: widget.tools.entries.map((entry) {
                return _ToolItem(
                  tool: entry.value,
                  isExpanded: _expandedTools.contains(entry.key),
                  onToggle: () {
                    setState(() {
                      if (_expandedTools.contains(entry.key)) {
                        _expandedTools.remove(entry.key);
                      } else {
                        _expandedTools.add(entry.key);
                      }
                    });
                  },
                );
              }).toList(),
            ),
          ),
      ],
    );
  }
}

class _ToolItem extends StatelessWidget {
  const _ToolItem({
    required this.tool,
    required this.isExpanded,
    required this.onToggle,
  });
  final RoomTool tool;
  final bool isExpanded;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: onToggle,
          borderRadius: BorderRadius.circular(8),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
            child: Row(
              children: [
                // Tool type icon
                Icon(_getToolIcon(tool), size: 14, color: _getToolColor(tool)),
                const SizedBox(width: 8),
                // Tool name
                Expanded(
                  child: Text(
                    tool.kind,
                    style: theme.textTheme.bodySmall?.copyWith(
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
                // Expand indicator if has description or params
                if (tool.description != null || tool.extraParameters.isNotEmpty)
                  Icon(
                    isExpanded ? Icons.expand_less : Icons.expand_more,
                    size: 16,
                    color: colorScheme.onSurfaceVariant,
                  ),
              ],
            ),
          ),
        ),

        // Expanded details
        if (isExpanded) ...[
          if (tool.description != null)
            Padding(
              padding: const EdgeInsets.only(left: 30, right: 8, bottom: 4),
              child: Text(
                tool.description!,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          if (tool.extraParameters.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(left: 30, right: 8, bottom: 4),
              child: Wrap(
                spacing: 4,
                runSpacing: 4,
                children: tool.extraParameters.entries.map((e) {
                  return Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 6,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: colorScheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      '${e.key}: ${e.value}',
                      style: theme.textTheme.labelSmall?.copyWith(
                        fontFamily: 'monospace',
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),
        ],
      ],
    );
  }

  IconData _getToolIcon(RoomTool tool) {
    if (tool.isRagTool) return Icons.search;
    if (tool.kind.contains('time') || tool.kind.contains('date')) {
      return Icons.schedule;
    }
    if (tool.kind.contains('user')) return Icons.person_outline;
    if (tool.kind.contains('location')) return Icons.location_on_outlined;
    return Icons.extension_outlined;
  }

  Color _getToolColor(RoomTool tool) {
    if (tool.isRagTool) return const Color(0xFF7C3AED);
    if (tool.kind.contains('time') || tool.kind.contains('date')) {
      return const Color(0xFF059669);
    }
    if (tool.kind.contains('user')) return const Color(0xFF2563EB);
    return const Color(0xFF6B7280);
  }
}
