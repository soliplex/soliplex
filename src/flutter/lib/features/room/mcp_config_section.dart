import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/models/room_models.dart';
import 'package:soliplex/core/network/connection_registry.dart';
import 'package:soliplex/core/providers/app_providers.dart';
import 'package:soliplex/core/services/mcp_token_service.dart';

/// Section showing MCP connection configuration for a room.
///
/// Only shown when room.allowMcp is true.
/// Allows users to:
/// - Generate an MCP token
/// - Copy the full connection config
/// - See which tools are MCP-enabled
class McpConfigSection extends ConsumerStatefulWidget {
  const McpConfigSection({required this.room, super.key});
  final Room room;

  @override
  ConsumerState<McpConfigSection> createState() => _McpConfigSectionState();
}

class _McpConfigSectionState extends ConsumerState<McpConfigSection> {
  McpTokenResponse? _token;
  bool _isLoading = false;
  String? _error;
  bool _isExpanded = true; // Start expanded to show config immediately
  bool _copied = false;

  @override
  void initState() {
    super.initState();
    // Auto-fetch token when MCP is allowed
    if (widget.room.allowMcp) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _fetchToken();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    // Get MCP-enabled tools
    final mcpTools = widget.room.tools.entries
        .where((e) => e.value.allowMcp)
        .map((e) => e.value)
        .toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Section header
        Text(
          'MCP SERVER',
          style: theme.textTheme.labelSmall?.copyWith(
            color: colorScheme.onSurfaceVariant,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.5,
          ),
        ),
        const SizedBox(height: 8),

        // Main card
        Container(
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerLow,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: colorScheme.outline.withValues(alpha: 0.1),
            ),
          ),
          child: Column(
            children: [
              // Info row
              Padding(
                padding: const EdgeInsets.all(12),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: widget.room.allowMcp
                            ? const Color(0xFF059669).withValues(alpha: 0.1)
                            : colorScheme.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Icon(
                        Icons.hub_outlined,
                        size: 20,
                        color: widget.room.allowMcp
                            ? const Color(0xFF059669)
                            : colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            widget.room.allowMcp
                                ? 'This room can be used as an MCP server'
                                : 'MCP server not enabled for this room',
                            style: theme.textTheme.bodyMedium,
                          ),
                          if (widget.room.allowMcp)
                            Text(
                              // ignore: lines_longer_than_80_chars (auto-documented)
                              '${mcpTools.length} tool${mcpTools.length == 1 ? '' : 's'} available via MCP',
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: colorScheme.onSurfaceVariant,
                              ),
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

              // Only show token button/config when MCP is allowed
              if (widget.room.allowMcp) ...[
                Divider(
                  height: 1,
                  color: colorScheme.outline.withValues(alpha: 0.1),
                ),

                // Token button or config display
                if (_token == null)
                  _buildGetTokenButton(context)
                else
                  _buildTokenConfig(context),
              ],

              // Error message
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: [
                      Icon(
                        Icons.error_outline,
                        size: 16,
                        color: colorScheme.error,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _error!,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: colorScheme.error,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),

        // MCP-enabled tools list (only when MCP is allowed)
        if (widget.room.allowMcp && mcpTools.isNotEmpty) ...[
          const SizedBox(height: 12),
          _buildMcpToolsList(context, mcpTools),
        ],
      ],
    );
  }

  Widget _buildGetTokenButton(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return InkWell(
      onTap: _isLoading ? null : _fetchToken,
      borderRadius: const BorderRadius.vertical(bottom: Radius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (_isLoading)
              SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: colorScheme.primary,
                ),
              )
            else
              Icon(Icons.key, size: 18, color: colorScheme.primary),
            const SizedBox(width: 8),
            Text(
              _isLoading ? 'Generating...' : 'Generate MCP Token',
              style: TextStyle(
                color: colorScheme.primary,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTokenConfig(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final config = _generateConfig();

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Token header with expiry info
          Row(
            children: [
              const Icon(Icons.check_circle, size: 18, color: Colors.green),
              const SizedBox(width: 8),
              Text(
                'Token',
                style: theme.textTheme.labelMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              const Spacer(),
              if (_token!.expiresIn != null)
                Text(
                  'Expires in ${_token!.expiresIn}',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 8),

          // Token value in selectable text field
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: colorScheme.outline.withValues(alpha: 0.2),
              ),
            ),
            child: SelectableText(
              _token!.token,
              style: theme.textTheme.bodySmall?.copyWith(
                fontFamily: 'monospace',
                fontSize: 12,
              ),
            ),
          ),
          const SizedBox(height: 8),

          // Copy token button (prominent)
          Row(
            children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: _copyToken,
                  icon: Icon(_copied ? Icons.check : Icons.copy, size: 16),
                  label: Text(_copied ? 'Copied!' : 'Copy Token'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                onPressed: _fetchToken,
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('Refresh'),
              ),
            ],
          ),

          // MCP Config section (expandable)
          const SizedBox(height: 16),
          InkWell(
            onTap: () => setState(() => _isExpanded = !_isExpanded),
            borderRadius: BorderRadius.circular(8),
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
              child: Row(
                children: [
                  Icon(
                    _isExpanded ? Icons.expand_less : Icons.expand_more,
                    size: 20,
                    color: colorScheme.onSurfaceVariant,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    'MCP Client Config',
                    style: theme.textTheme.labelMedium?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ),

          // Expanded MCP config
          if (_isExpanded) ...[
            const SizedBox(height: 8),
            Text(
              'Add to claude_desktop_config.json:',
              style: theme.textTheme.labelSmall?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(8),
              ),
              child: SelectableText(
                config ?? '',
                style: theme.textTheme.bodySmall?.copyWith(
                  fontFamily: 'monospace',
                  fontSize: 11,
                ),
              ),
            ),
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () => _copyConfig(config),
                icon: const Icon(Icons.copy, size: 16),
                label: const Text('Copy Config'),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildMcpToolsList(BuildContext context, List<RoomTool> tools) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Container(
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: colorScheme.outline.withValues(alpha: 0.1)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Icon(
                  Icons.build_outlined,
                  size: 16,
                  color: colorScheme.onSurfaceVariant,
                ),
                const SizedBox(width: 8),
                Text(
                  'MCP-Enabled Tools',
                  style: theme.textTheme.labelMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
          Divider(height: 1, color: colorScheme.outline.withValues(alpha: 0.1)),
          ...tools.map(
            (tool) => Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Row(
                children: [
                  Container(
                    width: 6,
                    height: 6,
                    decoration: const BoxDecoration(
                      color: Color(0xFF059669),
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      tool.toolName,
                      style: theme.textTheme.bodySmall?.copyWith(
                        fontFamily: 'monospace',
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 4),
        ],
      ),
    );
  }

  Future<void> _fetchToken() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final server = ref.read(currentServerFromAppStateProvider);
      if (server == null) {
        setState(() {
          _error = 'No server configured';
          _isLoading = false;
        });
        return;
      }

      // Get the transport layer for this server from the connection registry
      final registry = ref.read(connectionRegistryProvider);
      final serverState = registry.getServerState(server.id);
      final transportLayer = serverState?.transportLayer;

      final service = ref.read(mcpTokenServiceProvider);
      final token = await service.getToken(
        serverUrl: server.url,
        serverId: server.id,
        roomId: widget.room.id,
        transportLayer: transportLayer,
      );

      setState(() {
        _token = token;
        _isLoading = false;
        if (token == null) {
          _error = 'Failed to generate token';
        }
      });
    } on Object catch (e) {
      setState(() {
        _error = 'Error: $e';
        _isLoading = false;
      });
    }
  }

  String? _generateConfig() {
    if (_token == null) return null;

    final server = ref.read(currentServerFromAppStateProvider);
    if (server == null) return null;

    final service = ref.read(mcpTokenServiceProvider);
    return service.generateMcpConfig(
      serverUrl: server.url,
      roomId: widget.room.id,
      token: _token!.token,
    );
  }

  void _copyToken() {
    if (_token == null) return;

    Clipboard.setData(ClipboardData(text: _token!.token));
    setState(() => _copied = true);

    Future<void>.delayed(const Duration(seconds: 2), () {
      if (mounted) {
        setState(() => _copied = false);
      }
    });
  }

  void _copyConfig(String? config) {
    if (config == null) return;

    Clipboard.setData(ClipboardData(text: config));
    // Don't set _copied here to avoid conflict with token copy state
  }
}
