import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:soliplex/core/models/saved_endpoint.dart';
import 'package:soliplex/core/models/server_models.dart';
import 'package:soliplex/core/providers/app_providers.dart';
import 'package:soliplex/core/services/endpoint_config_service.dart';
import 'package:soliplex/features/endpoints/add_endpoint_dialog.dart';
import 'package:soliplex/features/endpoints/endpoint_tile.dart';

/// Screen displaying all saved endpoint configurations.
///
/// Allows users to:
/// - View all saved endpoints
/// - Add new endpoints
/// - Edit existing endpoints
/// - Delete endpoints
/// - Enable/disable endpoints
class EndpointListScreen extends ConsumerStatefulWidget {
  const EndpointListScreen({
    super.key,
    this.onEndpointSelected,
    this.selectedEndpointId,
  });

  /// Callback when an endpoint is selected for use.
  final void Function(SavedEndpoint endpoint)? onEndpointSelected;

  /// The currently selected endpoint ID (if any).
  final String? selectedEndpointId;

  @override
  ConsumerState<EndpointListScreen> createState() => _EndpointListScreenState();
}

class _EndpointListScreenState extends ConsumerState<EndpointListScreen> {
  /// Cache of which endpoints have API keys.
  final Map<String, bool> _apiKeyStatus = {};

  @override
  void initState() {
    super.initState();
    _loadApiKeyStatus();
  }

  Future<void> _loadApiKeyStatus() async {
    final service = ref.read(endpointConfigServiceProvider);
    final endpoints = await service.listEndpoints();

    final status = <String, bool>{};
    for (final endpoint in endpoints) {
      status[endpoint.id] = await service.hasApiKey(endpoint.id);
    }

    if (mounted) {
      setState(() {
        _apiKeyStatus.clear();
        _apiKeyStatus.addAll(status);
      });
    }
  }

  Future<void> _addEndpoint() async {
    final result = await AddEndpointDialog.show(context);
    if (result != null) {
      await _loadApiKeyStatus();
    }
  }

  Future<void> _editEndpoint(SavedEndpoint endpoint) async {
    final result = await AddEndpointDialog.show(
      context,
      existingEndpoint: endpoint,
    );
    if (result != null) {
      await _loadApiKeyStatus();
    }
  }

  Future<void> _deleteEndpoint(SavedEndpoint endpoint) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Endpoint'),
        content: Text(
          'Are you sure you want to delete "${endpoint.name}"? '
          'This will also remove the stored API key.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirmed ?? false) {
      final service = ref.read(endpointConfigServiceProvider);
      await service.deleteEndpoint(endpoint.id);
      ref.invalidate(endpointConfigsProvider);
      _apiKeyStatus.remove(endpoint.id);
    }
  }

  Future<void> _toggleEnabled(SavedEndpoint endpoint) async {
    final service = ref.read(endpointConfigServiceProvider);
    await service.toggleEnabled(endpoint.id);
    ref.invalidate(endpointConfigsProvider);
  }

  Future<void> _connectToEndpoint(SavedEndpoint endpoint) async {
    try {
      final appStateManager = ref.read(appStateManagerProvider);

      final serverInfo = ServerInfo(
        url: endpoint.url,
        isReachable: true,
        authDisabled: endpoint.isCompletions,
      );

      await appStateManager.setServer(
        serverInfo,
        displayName: endpoint.name,
        config: endpoint.config,
      );

      if (mounted) {
        context.go('/chat');
      }
    } on Object catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Failed to connect: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final endpointsAsync = ref.watch(endpointConfigsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Manage Endpoints'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'Add Endpoint',
            onPressed: _addEndpoint,
          ),
        ],
      ),
      body: endpointsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stack) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.error_outline,
                size: 48,
                color: theme.colorScheme.error,
              ),
              const SizedBox(height: 16),
              Text(
                'Failed to load endpoints',
                style: theme.textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              Text(error.toString(), style: theme.textTheme.bodySmall),
              const SizedBox(height: 16),
              FilledButton.tonal(
                onPressed: () => ref.invalidate(endpointConfigsProvider),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
        data: (endpoints) {
          if (endpoints.isEmpty) {
            return _buildEmptyState(context);
          }

          return ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: endpoints.length,
            itemBuilder: (context, index) {
              final endpoint = endpoints[index];
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: EndpointTile(
                  endpoint: endpoint,
                  hasApiKey: _apiKeyStatus[endpoint.id] ?? false,
                  isSelected: endpoint.id == widget.selectedEndpointId,
                  onTap: widget.onEndpointSelected != null
                      ? () => widget.onEndpointSelected!(endpoint)
                      : () => _connectToEndpoint(endpoint),
                  onEdit: () => _editEndpoint(endpoint),
                  onDelete: () => _deleteEndpoint(endpoint),
                  onToggleEnabled: () => _toggleEnabled(endpoint),
                ),
              );
            },
          );
        },
      ),
      floatingActionButton: endpointsAsync.maybeWhen(
        data: (endpoints) => endpoints.isEmpty
            ? FloatingActionButton.extended(
                onPressed: _addEndpoint,
                icon: const Icon(Icons.add),
                label: const Text('Add Endpoint'),
              )
            : null,
        orElse: () => null,
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    final theme = Theme.of(context);

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.cloud_off,
              size: 80,
              color: theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.5),
            ),
            const SizedBox(height: 24),
            Text(
              'No Endpoints Configured',
              style: theme.textTheme.headlineSmall,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              'Add an endpoint to connect to an AI service.\n'
              // ignore: lines_longer_than_80_chars (auto-documented)
              'You can connect to OpenAI, Anthropic, local models, or AG-UI servers.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            FilledButton.icon(
              onPressed: _addEndpoint,
              icon: const Icon(Icons.add),
              label: const Text('Add Your First Endpoint'),
            ),
          ],
        ),
      ),
    );
  }
}
