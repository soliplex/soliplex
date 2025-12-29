import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/models/room_models.dart';
import 'package:soliplex/core/services/local_tools_service.dart';
import 'package:soliplex/features/room/capability_badges.dart';
import 'package:soliplex/features/room/mcp_config_section.dart';
import 'package:soliplex/features/room/system_prompt_viewer.dart';
import 'package:soliplex/features/room/tools_list.dart';
import 'package:soliplex/features/room/widgets/background_image_section.dart';
import 'package:soliplex/features/room/widgets/document_list_dialog.dart';

/// A drawer showing detailed room information.
///
/// Displays:
/// - Room name and description
/// - Model/agent configuration
/// - Capability badges
/// - Tools list
/// - System prompt viewer
class RoomInfoDrawer extends StatelessWidget {
  const RoomInfoDrawer({required this.room, super.key});
  final Room room;

  /// Show the drawer as an end drawer in a Scaffold.
  static void show(BuildContext context, Room room) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Colors.transparent,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        minChildSize: 0.5,
        maxChildSize: 0.95,
        builder: (context, scrollController) => Container(
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
          ),
          child: _RoomInfoContent(
            room: room,
            scrollController: scrollController,
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Drawer(
      width: 360,
      child: SafeArea(child: _RoomInfoContent(room: room)),
    );
  }
}

class _RoomInfoContent extends ConsumerWidget {
  const _RoomInfoContent({required this.room, this.scrollController});
  final Room room;
  final ScrollController? scrollController;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    // Get client-side tools
    final localTools = ref.watch(localToolsServiceProvider).tools;
    final clientToolsMap = <String, RoomTool>{
      for (final tool in localTools)
        tool.name: RoomTool(
          id: tool.name,
          kind: tool.name,
          toolName: tool.name,
          description: tool.description,
          extraParameters: tool.parameters,
        ),
    };

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header with drag handle (for bottom sheet) or close button
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            border: Border(
              bottom: BorderSide(
                color: colorScheme.outline.withValues(alpha: 0.2),
              ),
            ),
          ),
          child: Column(
            children: [
              // Drag handle for bottom sheet
              if (scrollController != null)
                Container(
                  width: 40,
                  height: 4,
                  margin: const EdgeInsets.only(bottom: 12),
                  decoration: BoxDecoration(
                    color: colorScheme.onSurfaceVariant.withValues(alpha: 0.4),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              Row(
                children: [
                  // Room icon
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: colorScheme.primaryContainer,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      Icons.meeting_room,
                      color: colorScheme.onPrimaryContainer,
                      size: 24,
                    ),
                  ),
                  const SizedBox(width: 12),
                  // Room name and model
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          room.name,
                          style: theme.textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        if (room.agent != null)
                          Text(
                            room.agent!.displayModelName,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: colorScheme.onSurfaceVariant,
                            ),
                          ),
                      ],
                    ),
                  ),
                  // Close button
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.of(context).pop(),
                    tooltip: 'Close',
                  ),
                ],
              ),
            ],
          ),
        ),

        // Scrollable content
        Expanded(
          child: ListView(
            controller: scrollController,
            padding: const EdgeInsets.all(16),
            children: [
              // Description
              if (room.description != null && room.description!.isNotEmpty) ...[
                const _SectionHeader(title: 'Description'),
                const SizedBox(height: 8),
                Text(
                  room.description!,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 20),
              ],

              // Capability badges
              const _SectionHeader(title: 'Capabilities'),
              const SizedBox(height: 8),
              CapabilityBadges(
                room: room,
                clientToolCount: clientToolsMap.length,
              ),
              const SizedBox(height: 20),

              // Background Image
              BackgroundImageSection(room: room),
              const SizedBox(height: 20),

              // Model info
              if (room.agent != null) ...[
                const _SectionHeader(title: 'Model'),
                const SizedBox(height: 8),
                _InfoCard(
                  children: [
                    _InfoRow(
                      icon: Icons.smart_toy_outlined,
                      label: 'Model',
                      value: room.agent!.displayModelName,
                    ),
                    _InfoRow(
                      icon: Icons.cloud_outlined,
                      label: 'Provider',
                      value: room.agent!.displayProvider,
                    ),
                    if (!room.agent!.isFactory)
                      _InfoRow(
                        icon: Icons.refresh,
                        label: 'Retries',
                        value: '${room.agent!.retries}',
                      ),
                  ],
                ),
                const SizedBox(height: 20),
              ],

              // Room Tools list
              if (room.tools.isNotEmpty) ...[
                ToolsList(
                  tools: room.tools,
                  title: 'Room Tools',
                  icon: Icons.cloud_outlined,
                ),
                const SizedBox(height: 20),
              ],

              // Client Tools list
              if (clientToolsMap.isNotEmpty) ...[
                ToolsList(
                  tools: clientToolsMap,
                  title: 'Client Tools',
                  icon: Icons.devices,
                ),
                const SizedBox(height: 20),
              ],

              // MCP Client toolsets (toolsets this room connects TO)
              if (room.mcpClientToolsets.isNotEmpty) ...[
                const _SectionHeader(title: 'MCP Client Toolsets'),
                const SizedBox(height: 8),
                _InfoCard(
                  children: room.mcpClientToolsets.entries.map((entry) {
                    final toolset = entry.value;
                    return _InfoRow(
                      icon: toolset.kind == 'http'
                          ? Icons.http
                          : Icons.terminal,
                      label: entry.key,
                      value: toolset.kind.toUpperCase(),
                      subtitle: toolset.url ?? toolset.command,
                    );
                  }).toList(),
                ),
                const SizedBox(height: 20),
              ],

              // System prompt
              if (room.agent?.systemPrompt != null &&
                  room.agent!.systemPrompt!.isNotEmpty) ...[
                SystemPromptViewer(systemPrompt: room.agent!.systemPrompt),
                const SizedBox(height: 20),
              ],

              // Documents section
              if (room.hasRag) ...[
                // Using hasRag getter from Room model
                const _SectionHeader(title: 'Documents'),
                const SizedBox(height: 8),
                ListTile(
                  leading: const Icon(Icons.description_outlined),
                  title: const Text('View Documents'),
                  trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                  onTap: () {
                    Navigator.of(context).pop(); // Close drawer
                    showDialog(
                      context: context,
                      builder: (context) => DocumentListDialog(roomId: room.id),
                    );
                  },
                ),
                const SizedBox(height: 20),
              ],

              // Feature flags
              const _SectionHeader(title: 'Features'),
              const SizedBox(height: 8),
              _InfoCard(
                children: [
                  _FeatureRow(
                    icon: Icons.attach_file,
                    label: 'Attachments',
                    enabled: room.enableAttachments,
                  ),
                  _FeatureRow(
                    icon: Icons.hub_outlined,
                    label: 'MCP Allowed',
                    enabled: room.allowMcp,
                  ),
                ],
              ),

              // MCP Server config section (always shown)
              const SizedBox(height: 20),
              McpConfigSection(room: room),
            ],
          ),
        ),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title});
  final String title;

  @override
  Widget build(BuildContext context) {
    return Text(
      title.toUpperCase(),
      style: Theme.of(context).textTheme.labelSmall?.copyWith(
        color: Theme.of(context).colorScheme.onSurfaceVariant,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.5,
      ),
    );
  }
}

class _InfoCard extends StatelessWidget {
  const _InfoCard({required this.children});
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: colorScheme.outline.withValues(alpha: 0.1)),
      ),
      child: Column(
        children: [
          for (int i = 0; i < children.length; i++) ...[
            children[i],
            if (i < children.length - 1)
              Divider(
                height: 1,
                indent: 48,
                color: colorScheme.outline.withValues(alpha: 0.1),
              ),
          ],
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.icon,
    required this.label,
    required this.value,
    this.subtitle,
  });
  final IconData icon;
  final String label;
  final String value;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      child: Row(
        children: [
          Icon(icon, size: 18, color: colorScheme.onSurfaceVariant),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
                if (subtitle != null)
                  Text(
                    subtitle!,
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: colorScheme.onSurfaceVariant.withValues(
                        alpha: 0.7,
                      ),
                      fontFamily: 'monospace',
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
              ],
            ),
          ),
          Text(
            value,
            style: theme.textTheme.bodyMedium?.copyWith(
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}

class _FeatureRow extends StatelessWidget {
  const _FeatureRow({
    required this.icon,
    required this.label,
    required this.enabled,
  });
  final IconData icon;
  final String label;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      child: Row(
        children: [
          Icon(icon, size: 18, color: colorScheme.onSurfaceVariant),
          const SizedBox(width: 12),
          Expanded(child: Text(label, style: theme.textTheme.bodyMedium)),
          Icon(
            enabled ? Icons.check_circle : Icons.cancel_outlined,
            size: 18,
            color: enabled ? Colors.green : colorScheme.onSurfaceVariant,
          ),
        ],
      ),
    );
  }
}
