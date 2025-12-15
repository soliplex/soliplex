import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex/core/models/endpoint_models.dart';
import 'package:soliplex/core/models/saved_endpoint.dart';
import 'package:soliplex/core/services/secure_storage_service.dart';
import 'package:soliplex/core/utils/debug_log.dart';

/// Storage key for endpoint configurations.
const _endpointConfigKey = 'endpoint_configs';

/// Service for managing endpoint configurations.
///
/// Handles CRUD operations for endpoint configs with persistence via
/// SecureStorageService. API keys are stored separately for security.
class EndpointConfigService {
  EndpointConfigService(this._storage);
  final SecureStorageService _storage;

  /// Cached endpoint configs (loaded lazily).
  List<SavedEndpoint>? _cachedConfigs;

  /// Get all saved endpoint configurations.
  Future<List<SavedEndpoint>> listEndpoints() async {
    if (_cachedConfigs != null) {
      return List.unmodifiable(_cachedConfigs!);
    }

    final data = await _storage.read(_endpointConfigKey);
    if (data == null || data.isEmpty) {
      _cachedConfigs = [];
      return [];
    }

    try {
      final list = jsonDecode(data) as List;
      _cachedConfigs = list
          .map((e) => SavedEndpoint.fromJson(e as Map<String, dynamic>))
          .toList();
      DebugLog.service(
        'EndpointConfigService: Loaded ${_cachedConfigs!.length} endpoints',
      );
      return List.unmodifiable(_cachedConfigs!);
    } on Object catch (e) {
      DebugLog.warn('EndpointConfigService: Failed to parse configs: $e');
      _cachedConfigs = [];
      return [];
    }
  }

  /// Get a specific endpoint by ID.
  Future<SavedEndpoint?> getEndpoint(String id) async {
    final endpoints = await listEndpoints();
    try {
      return endpoints.firstWhere((e) => e.id == id);
    } on Object catch (_) {
      return null;
    }
  }

  /// Save or update an endpoint configuration.
  ///
  /// If an endpoint with the same ID exists, it will be updated.
  /// Otherwise, a new endpoint will be created.
  Future<void> saveEndpoint(SavedEndpoint config) async {
    final endpoints = await listEndpoints();
    final index = endpoints.indexWhere((e) => e.id == config.id);

    final mutableList = List<SavedEndpoint>.from(endpoints);
    if (index >= 0) {
      mutableList[index] = config;
      DebugLog.service('EndpointConfigService: Updated endpoint ${config.id}');
    } else {
      mutableList.add(config);
      DebugLog.service('EndpointConfigService: Added endpoint ${config.id}');
    }

    await _persistEndpoints(mutableList);
  }

  /// Delete an endpoint configuration.
  ///
  /// Also deletes any associated API key.
  Future<void> deleteEndpoint(String id) async {
    final endpoints = await listEndpoints();
    final mutableList = endpoints.where((e) => e.id != id).toList();

    // Delete associated API key
    await _storage.deleteApiKey(id);

    await _persistEndpoints(mutableList);
    DebugLog.service('EndpointConfigService: Deleted endpoint $id');
  }

  /// Get the API key for an endpoint.
  Future<String?> getApiKey(String endpointId) async {
    return _storage.getApiKey(endpointId);
  }

  /// Save the API key for an endpoint.
  Future<void> saveApiKey(String endpointId, String apiKey) async {
    await _storage.storeApiKey(endpointId: endpointId, apiKey: apiKey);
    DebugLog.service('EndpointConfigService: Saved API key for $endpointId');
  }

  /// Check if an endpoint has an API key stored.
  Future<bool> hasApiKey(String endpointId) async {
    return _storage.hasApiKey(endpointId);
  }

  /// Delete the API key for an endpoint.
  Future<void> deleteApiKey(String endpointId) async {
    await _storage.deleteApiKey(endpointId);
    DebugLog.service('EndpointConfigService: Deleted API key for $endpointId');
  }

  /// Get all completions endpoints.
  Future<List<SavedEndpoint>> listCompletionsEndpoints() async {
    final endpoints = await listEndpoints();
    return endpoints.where((e) => e.config is CompletionsEndpoint).toList();
  }

  /// Get all AG-UI endpoints.
  Future<List<SavedEndpoint>> listAgUiEndpoints() async {
    final endpoints = await listEndpoints();
    return endpoints.where((e) => e.config is AgUiEndpoint).toList();
  }

  /// Get enabled endpoints only.
  Future<List<SavedEndpoint>> listEnabledEndpoints() async {
    final endpoints = await listEndpoints();
    return endpoints.where((e) => e.isEnabled).toList();
  }

  /// Toggle the enabled state of an endpoint.
  Future<void> toggleEnabled(String id) async {
    final endpoint = await getEndpoint(id);
    if (endpoint == null) return;

    await saveEndpoint(endpoint.copyWith(isEnabled: !endpoint.isEnabled));
  }

  /// Invalidate the cache (forces reload on next access).
  void invalidateCache() {
    _cachedConfigs = null;
    DebugLog.service('EndpointConfigService: Cache invalidated');
  }

  /// Persist endpoints to storage.
  Future<void> _persistEndpoints(List<SavedEndpoint> endpoints) async {
    _cachedConfigs = endpoints;
    final json = jsonEncode(endpoints.map((e) => e.toJson()).toList());
    await _storage.write(_endpointConfigKey, json);
  }
}

// =============================================================================
// Providers
// =============================================================================

/// Provider for EndpointConfigService.
final endpointConfigServiceProvider = Provider<EndpointConfigService>((ref) {
  final storage = ref.watch(secureStorageProvider);
  return EndpointConfigService(storage);
});

/// Provider for the list of all endpoint configurations.
///
/// This is a FutureProvider that loads endpoints from storage.
/// Use `ref.refresh()` to reload after modifications.
final endpointConfigsProvider = FutureProvider<List<SavedEndpoint>>((
  ref,
) async {
  final service = ref.watch(endpointConfigServiceProvider);
  return service.listEndpoints();
});

/// Provider for completions endpoints only.
final completionsEndpointsProvider = FutureProvider<List<SavedEndpoint>>((
  ref,
) async {
  final service = ref.watch(endpointConfigServiceProvider);
  return service.listCompletionsEndpoints();
});

/// Provider for AG-UI endpoints only.
final agUiEndpointsProvider = FutureProvider<List<SavedEndpoint>>((ref) async {
  final service = ref.watch(endpointConfigServiceProvider);
  return service.listAgUiEndpoints();
});
