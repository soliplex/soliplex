import 'package:flutter/material.dart';

import 'package:soliplex/core/models/endpoint_models.dart';
import 'package:soliplex/core/models/saved_endpoint.dart';

/// A tile displaying an endpoint configuration.
///
/// Shows the endpoint name, URL, type, and status with actions for
/// edit, delete, and enable/disable.
class EndpointTile extends StatelessWidget {
  const EndpointTile({
    required this.endpoint,
    super.key,
    this.hasApiKey = false,
    this.isSelected = false,
    this.onTap,
    this.onEdit,
    this.onDelete,
    this.onToggleEnabled,
  });
  final SavedEndpoint endpoint;
  final bool hasApiKey;
  final bool isSelected;
  final VoidCallback? onTap;
  final VoidCallback? onEdit;
  final VoidCallback? onDelete;
  final VoidCallback? onToggleEnabled;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final config = endpoint.config;
    final type = config.type;

    return Card(
      elevation: isSelected ? 2 : 0,
      color: isSelected
          ? colorScheme.primaryContainer
          : endpoint.isEnabled
          ? null
          : colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
      child: InkWell(
        onTap: endpoint.isEnabled ? onTap : null,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              // Type icon
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: endpoint.isEnabled
                      ? colorScheme.primaryContainer
                      : colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  type.icon,
                  color: endpoint.isEnabled
                      ? colorScheme.onPrimaryContainer
                      : colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(width: 16),

              // Name and URL
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            endpoint.name,
                            style: theme.textTheme.titleMedium?.copyWith(
                              color: endpoint.isEnabled
                                  ? null
                                  : colorScheme.onSurfaceVariant,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        if (!endpoint.isEnabled)
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: colorScheme.surfaceContainerHighest,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              'Disabled',
                              style: theme.textTheme.labelSmall?.copyWith(
                                color: colorScheme.onSurfaceVariant,
                              ),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      endpoint.url,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 8),
                    // Badges row
                    Wrap(
                      spacing: 8,
                      runSpacing: 4,
                      children: [
                        _buildBadge(
                          context,
                          type.displayName,
                          colorScheme.secondaryContainer,
                          colorScheme.onSecondaryContainer,
                        ),
                        if (endpoint.isCompletions &&
                            config is CompletionsEndpoint)
                          _buildBadge(
                            context,
                            config.model,
                            colorScheme.tertiaryContainer,
                            colorScheme.onTertiaryContainer,
                          ),
                        if (type.requiresAuthByDefault && !hasApiKey)
                          _buildBadge(
                            context,
                            'No API Key',
                            colorScheme.errorContainer,
                            colorScheme.onErrorContainer,
                            icon: Icons.warning_amber_rounded,
                          ),
                        if (hasApiKey)
                          _buildBadge(
                            context,
                            'API Key Set',
                            colorScheme.primaryContainer,
                            colorScheme.onPrimaryContainer,
                            icon: Icons.key,
                          ),
                      ],
                    ),
                  ],
                ),
              ),

              // Actions
              PopupMenuButton<String>(
                icon: const Icon(Icons.more_vert),
                onSelected: (value) {
                  switch (value) {
                    case 'edit':
                      onEdit?.call();
                    case 'delete':
                      onDelete?.call();
                    case 'toggle':
                      onToggleEnabled?.call();
                  }
                },
                itemBuilder: (context) => [
                  const PopupMenuItem(
                    value: 'edit',
                    child: ListTile(
                      leading: Icon(Icons.edit),
                      title: Text('Edit'),
                      contentPadding: EdgeInsets.zero,
                    ),
                  ),
                  PopupMenuItem(
                    value: 'toggle',
                    child: ListTile(
                      leading: Icon(
                        endpoint.isEnabled
                            ? Icons.visibility_off
                            : Icons.visibility,
                      ),
                      title: Text(endpoint.isEnabled ? 'Disable' : 'Enable'),
                      contentPadding: EdgeInsets.zero,
                    ),
                  ),
                  const PopupMenuDivider(),
                  const PopupMenuItem(
                    value: 'delete',
                    child: ListTile(
                      leading: Icon(Icons.delete, color: Colors.red),
                      title: Text(
                        'Delete',
                        style: TextStyle(color: Colors.red),
                      ),
                      contentPadding: EdgeInsets.zero,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBadge(
    BuildContext context,
    String label,
    Color backgroundColor,
    Color textColor, {
    IconData? icon,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 12, color: textColor),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: Theme.of(
              context,
            ).textTheme.labelSmall?.copyWith(color: textColor),
          ),
        ],
      ),
    );
  }
}
