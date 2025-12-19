import 'package:flutter/material.dart';

import 'package:soliplex/core/models/room_models.dart';

/// Badge types for room capabilities.
enum CapabilityType { rag, tools, mcp, attachments, factory }

/// A row of capability badges showing room features at a glance.
///
/// Displays color-coded pills for capabilities like RAG, Tools, MCP, etc.
/// Badges can be tapped to show tooltips with more details.
class CapabilityBadges extends StatelessWidget {
  const CapabilityBadges({
    required this.room,
    super.key,
    this.compact = false,
    this.onBadgeTap,
    this.clientToolCount,
  });
  final Room room;
  final bool compact;
  final void Function(CapabilityType)? onBadgeTap;
  final int? clientToolCount;

  @override
  Widget build(BuildContext context) {
    final badges = <Widget>[];

    // RAG badge (if room has RAG tools)
    if (room.hasRag) {
      badges.add(
        _CapabilityBadge(
          type: CapabilityType.rag,
          label: compact ? 'RAG' : 'RAG',
          tooltip: 'Has document search capabilities',
          color: _badgeColor(CapabilityType.rag),
          icon: Icons.search,
          onTap: () => onBadgeTap?.call(CapabilityType.rag),
        ),
      );
    }

    // Tools breakdown
    if (clientToolCount != null) {
      // Server Tools
      if (room.toolCount > 0) {
        badges.add(
          _CapabilityBadge(
            type: CapabilityType.tools,
            label: compact ? '${room.toolCount}S' : '${room.toolCount} Server',
            tooltip: '${room.toolCount} server-side tools available',
            color: const Color(0xFF2563EB), // Blue
            icon: Icons.dns_outlined,
            onTap: () => onBadgeTap?.call(CapabilityType.tools),
          ),
        );
      }
      // Client Tools
      if (clientToolCount! > 0) {
        badges.add(
          _CapabilityBadge(
            type: CapabilityType.tools,
            label: compact ? '${clientToolCount}C' : '$clientToolCount Client',
            tooltip: '$clientToolCount client-side tools available',
            color: const Color(0xFF059669), // Green
            icon: Icons.devices,
            onTap: () => onBadgeTap?.call(CapabilityType.tools),
          ),
        );
      }
    } else {
      // Legacy generic Tools badge
      if (room.toolCount > 0) {
        badges.add(
          _CapabilityBadge(
            type: CapabilityType.tools,
            label: compact ? '${room.toolCount}T' : '${room.toolCount} Tools',
            tooltip: 'Has ${room.toolCount} tools available',
            color: _badgeColor(CapabilityType.tools),
            icon: Icons.build_outlined,
            onTap: () => onBadgeTap?.call(CapabilityType.tools),
          ),
        );
      }
    }

    // MCP badge (if room has MCP integrations)
    if (room.hasMcp) {
      badges.add(
        _CapabilityBadge(
          type: CapabilityType.mcp,
          label: compact ? 'MCP' : 'MCP',
          tooltip:
              // ignore: lines_longer_than_80_chars (auto-documented)
              '${room.mcpToolsetCount} MCP toolset${room.mcpToolsetCount > 1 ? 's' : ''} connected',
          color: _badgeColor(CapabilityType.mcp),
          icon: Icons.hub_outlined,
          onTap: () => onBadgeTap?.call(CapabilityType.mcp),
        ),
      );
    }

    // Attachments badge
    if (room.enableAttachments) {
      badges.add(
        _CapabilityBadge(
          type: CapabilityType.attachments,
          label: compact ? 'ATT' : 'Attachments',
          tooltip: 'File attachments enabled',
          color: _badgeColor(CapabilityType.attachments),
          icon: Icons.attach_file,
          onTap: () => onBadgeTap?.call(CapabilityType.attachments),
        ),
      );
    }

    // Factory agent badge
    if (room.agent?.isFactory ?? false) {
      badges.add(
        _CapabilityBadge(
          type: CapabilityType.factory,
          label: compact ? 'FAC' : 'Factory',
          tooltip: 'Uses a custom agent factory',
          color: _badgeColor(CapabilityType.factory),
          icon: Icons.factory_outlined,
          onTap: () => onBadgeTap?.call(CapabilityType.factory),
        ),
      );
    }

    if (badges.isEmpty) {
      return const SizedBox.shrink();
    }

    return Wrap(spacing: 6, runSpacing: 4, children: badges);
  }

  Color _badgeColor(CapabilityType type) {
    switch (type) {
      case CapabilityType.rag:
        return const Color(0xFF7C3AED); // Purple
      case CapabilityType.tools:
        return const Color(0xFF2563EB); // Blue
      case CapabilityType.mcp:
        return const Color(0xFF059669); // Green
      case CapabilityType.attachments:
        return const Color(0xFFD97706); // Amber
      case CapabilityType.factory:
        return const Color(0xFFDC2626); // Red
    }
  }
}

class _CapabilityBadge extends StatelessWidget {
  const _CapabilityBadge({
    required this.type,
    required this.label,
    required this.tooltip,
    required this.color,
    required this.icon,
    this.onTap,
  });
  final CapabilityType type;
  final String label;
  final String tooltip;
  final Color color;
  final IconData icon;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: color.withValues(alpha: 0.3)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 12, color: color),
              const SizedBox(width: 4),
              Text(
                label,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: color,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// A single capability indicator (minimal style for tight spaces).
class CapabilityIndicator extends StatelessWidget {
  const CapabilityIndicator({
    required this.icon,
    required this.color,
    required this.tooltip,
    super.key,
  });
  final IconData icon;
  final Color color;
  final String tooltip;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: Icon(icon, size: 14, color: color),
    );
  }
}

/// Quick capability icons row (very compact).
class CapabilityIcons extends StatelessWidget {
  const CapabilityIcons({required this.room, super.key});
  final Room room;

  @override
  Widget build(BuildContext context) {
    final indicators = <Widget>[];

    if (room.hasRag) {
      indicators.add(
        const CapabilityIndicator(
          icon: Icons.search,
          color: Color(0xFF7C3AED),
          tooltip: 'RAG enabled',
        ),
      );
    }

    if (room.toolCount > 0) {
      indicators.add(
        CapabilityIndicator(
          icon: Icons.build_outlined,
          color: const Color(0xFF2563EB),
          tooltip: '${room.toolCount} tools',
        ),
      );
    }

    if (room.hasMcp) {
      indicators.add(
        const CapabilityIndicator(
          icon: Icons.hub_outlined,
          color: Color(0xFF059669),
          tooltip: 'MCP connected',
        ),
      );
    }

    if (room.enableAttachments) {
      indicators.add(
        const CapabilityIndicator(
          icon: Icons.attach_file,
          color: Color(0xFFD97706),
          tooltip: 'Attachments enabled',
        ),
      );
    }

    if (indicators.isEmpty) {
      return const SizedBox.shrink();
    }

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (int i = 0; i < indicators.length; i++) ...[
          indicators[i],
          if (i < indicators.length - 1) const SizedBox(width: 4),
        ],
      ],
    );
  }
}
