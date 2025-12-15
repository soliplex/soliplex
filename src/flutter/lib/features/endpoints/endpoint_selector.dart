import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:soliplex/core/models/endpoint_models.dart';
import 'package:soliplex/core/services/completions_session_manager.dart';
import 'package:soliplex/core/services/endpoint_config_service.dart';

/// Compact endpoint selector for the chat screen app bar.
///
/// Shows:
/// - Current mode (AG-UI or selected endpoint name)
/// - Dropdown to switch endpoints or return to AG-UI mode
class EndpointSelector extends ConsumerWidget {
  const EndpointSelector({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final sessionState = ref.watch(completionsSessionManagerProvider);
    final endpointsAsync = ref.watch(completionsEndpointsProvider);

    final activeEndpoint = sessionState.activeEndpoint;
    final isLoading = sessionState.isLoading;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: activeEndpoint != null
            ? colorScheme.tertiaryContainer
            : colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: PopupMenuButton<String>(
        tooltip: 'Select endpoint',
        offset: const Offset(0, 40),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (isLoading)
              const SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            else
              Icon(
                activeEndpoint != null ? Icons.cloud : Icons.smart_toy,
                size: 16,
                color: activeEndpoint != null
                    ? colorScheme.onTertiaryContainer
                    : colorScheme.onSurfaceVariant,
              ),
            const SizedBox(width: 6),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 120),
              child: Text(
                activeEndpoint?.name ?? 'AG-UI',
                style: theme.textTheme.labelMedium?.copyWith(
                  color: activeEndpoint != null
                      ? colorScheme.onTertiaryContainer
                      : colorScheme.onSurfaceVariant,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            const SizedBox(width: 4),
            Icon(
              Icons.arrow_drop_down,
              size: 18,
              color: activeEndpoint != null
                  ? colorScheme.onTertiaryContainer
                  : colorScheme.onSurfaceVariant,
            ),
          ],
        ),
        itemBuilder: (context) => [
          // AG-UI mode option
          PopupMenuItem<String>(
            value: '_agui',
            child: ListTile(
              leading: Icon(
                Icons.smart_toy,
                color: activeEndpoint == null ? colorScheme.primary : null,
              ),
              title: const Text('AG-UI Mode'),
              subtitle: const Text('Use connected server rooms'),
              selected: activeEndpoint == null,
              contentPadding: EdgeInsets.zero,
            ),
          ),
          const PopupMenuDivider(),
          // Header for completions
          PopupMenuItem<String>(
            enabled: false,
            height: 32,
            child: Text(
              'Completions Endpoints',
              style: theme.textTheme.labelSmall?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          // Completions endpoints
          ...endpointsAsync.when(
            data: (endpoints) {
              if (endpoints.isEmpty) {
                return [
                  PopupMenuItem<String>(
                    enabled: false,
                    child: Text(
                      'No endpoints configured',
                      style: TextStyle(
                        color: colorScheme.onSurfaceVariant,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  ),
                ];
              }
              return endpoints.where((e) => e.isEnabled).map((endpoint) {
                final config = endpoint.config as CompletionsEndpoint;
                return PopupMenuItem<String>(
                  value: endpoint.id,
                  child: ListTile(
                    leading: Icon(
                      Icons.cloud,
                      color: activeEndpoint?.id == endpoint.id
                          ? colorScheme.primary
                          : null,
                    ),
                    title: Text(endpoint.name),
                    subtitle: Text(config.model),
                    selected: activeEndpoint?.id == endpoint.id,
                    contentPadding: EdgeInsets.zero,
                  ),
                );
              }).toList();
            },
            loading: () => [
              const PopupMenuItem<String>(
                enabled: false,
                child: Center(child: CircularProgressIndicator()),
              ),
            ],
            error: (error, stack) => [
              PopupMenuItem<String>(
                enabled: false,
                child: Text(
                  'Error loading endpoints',
                  style: TextStyle(color: colorScheme.error),
                ),
              ),
            ],
          ),
        ],
        onSelected: (value) async {
          final manager = ref.read(completionsSessionManagerProvider.notifier);

          if (value == '_agui') {
            await manager.clearEndpoint();
          } else {
            // Find and select the endpoint
            final endpoints = await ref
                .read(endpointConfigServiceProvider)
                .listEndpoints();
            final endpoint = endpoints.firstWhere(
              (e) => e.id == value,
              orElse: () => throw StateError('Endpoint not found'),
            );
            await manager.selectEndpoint(endpoint);
          }
        },
      ),
    );
  }
}
