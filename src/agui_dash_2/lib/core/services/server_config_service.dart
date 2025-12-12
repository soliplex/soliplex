import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:uuid/uuid.dart';

import '../models/server_models.dart';
import '../utils/url_builder.dart';
import 'secure_storage_service.dart';

// Re-export models for convenience
export '../models/server_models.dart';

/// Service for server discovery and configuration management.
///
/// **DEPRECATED**: Use [ServerRegistry] and [AppStateManager] instead.
/// This class uses ChangeNotifier which causes cascading provider
/// invalidations. The new architecture uses stream-based state management.
///
/// Handles:
/// - Probing servers to discover capabilities
/// - Managing server connection history
/// - URL validation and normalization
@Deprecated('Use ServerRegistry and AppStateManager instead')
class ServerConfigService extends ChangeNotifier {
  final SecureStorageService _storage;
  final http.Client _httpClient;

  List<ServerConnection> _serverHistory = [];
  ServerConnection? _currentServer;
  bool _isLoading = false;
  String? _error;

  ServerConfigService({
    SecureStorageService? storage,
    http.Client? httpClient,
  })  : _storage = storage ?? SecureStorageFactory.create(),
        _httpClient = httpClient ?? http.Client();

  // Getters
  List<ServerConnection> get serverHistory => List.unmodifiable(_serverHistory);
  ServerConnection? get currentServer => _currentServer;
  bool get isLoading => _isLoading;
  String? get error => _error;
  bool get hasServer => _currentServer != null;

  /// Initialize the service, loading saved state
  Future<void> initialize() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      // Load server history
      final historyJson = await _storage.loadServerHistory();
      _serverHistory = historyJson
          .map((json) => ServerConnection.fromJson(json))
          .toList();

      // Sort by last connected (most recent first)
      _serverHistory.sort((a, b) => b.lastConnected.compareTo(a.lastConnected));

      // Load current server ID
      final currentId = await _storage.getCurrentServerId();
      if (currentId != null) {
        _currentServer = _serverHistory.firstWhere(
          (s) => s.id == currentId,
          orElse: () => _serverHistory.isNotEmpty ? _serverHistory.first : throw StateError('No servers'),
        );
      }
    } catch (e) {
      debugPrint('ServerConfigService: Error loading state: $e');
      // Not a fatal error, just start fresh
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Normalize a server URL (ensure https://, strip trailing slash and /api path).
  ///
  /// Delegates to [UrlBuilder.normalizeBaseUrl] for consistent URL handling.
  String normalizeUrl(String url) {
    return UrlBuilder.normalizeBaseUrl(url);
  }

  /// Probe a server to discover its capabilities
  Future<ServerInfo> probeServer(String url) async {
    final normalizedUrl = normalizeUrl(url);
    final urlBuilder = UrlBuilder(normalizedUrl);

    try {
      // Try to fetch /api/login endpoint to discover OIDC providers
      final loginUrl = urlBuilder.login();
      final response = await _httpClient
          .get(loginUrl)
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        // Parse OIDC providers from response
        final data = jsonDecode(response.body);
        final providers = _parseOidcProviders(data);

        return ServerInfo.fromProbe(
          url: normalizedUrl,
          providers: providers,
        );
      } else if (response.statusCode == 404) {
        // /login not found - might be an older server or auth disabled
        // Try /rooms to verify it's a Soliplex server
        return await _probeRoomsEndpoint(normalizedUrl);
      } else {
        return ServerInfo.unreachable(
          normalizedUrl,
          'Server returned status ${response.statusCode}',
        );
      }
    } on TimeoutException {
      return ServerInfo.unreachable(normalizedUrl, 'Connection timed out');
    } catch (e) {
      return ServerInfo.unreachable(normalizedUrl, e.toString());
    }
  }

  /// Fallback probe using /api/v1/rooms endpoint
  Future<ServerInfo> _probeRoomsEndpoint(String url) async {
    final urlBuilder = UrlBuilder(url);
    try {
      final roomsUrl = urlBuilder.rooms();
      final response = await _httpClient
          .get(roomsUrl)
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        // Server is reachable and auth is disabled (no 401)
        return ServerInfo(
          url: url,
          isReachable: true,
          authDisabled: true,
        );
      } else if (response.statusCode == 401) {
        // Server requires auth but /login wasn't found
        // This shouldn't happen with a properly configured server
        return ServerInfo.unreachable(
          url,
          'Server requires authentication but no OIDC providers found',
        );
      } else {
        return ServerInfo.unreachable(
          url,
          'Server returned status ${response.statusCode}',
        );
      }
    } catch (e) {
      return ServerInfo.unreachable(url, e.toString());
    }
  }

  /// Parse OIDC providers from /login response
  List<OIDCAuthSystem> _parseOidcProviders(dynamic data) {
    final providers = <OIDCAuthSystem>[];

    if (data is Map<String, dynamic>) {
      // Handle map of providers: {"keycloak": {...}, "google": {...}}
      data.forEach((key, value) {
        if (value is Map<String, dynamic>) {
          try {
            providers.add(OIDCAuthSystem.fromJson({
              'id': key,
              ...value,
            }));
          } catch (e) {
            debugPrint('Failed to parse OIDC provider $key: $e');
          }
        }
      });
    } else if (data is List) {
      // Handle list of providers: [{...}, {...}]
      for (final item in data) {
        if (item is Map<String, dynamic>) {
          try {
            providers.add(OIDCAuthSystem.fromJson(item));
          } catch (e) {
            debugPrint('Failed to parse OIDC provider: $e');
          }
        }
      }
    }

    return providers;
  }

  /// Connect to a server (after successful probe)
  Future<ServerConnection> connectToServer(
    ServerInfo serverInfo, {
    String? displayName,
  }) async {
    if (!serverInfo.isReachable) {
      throw StateError('Cannot connect to unreachable server');
    }

    // Check if we already have this server in history
    var connection = _serverHistory.firstWhere(
      (s) => s.url == serverInfo.url,
      orElse: () => ServerConnection(
        id: const Uuid().v4(),
        url: serverInfo.url,
        displayName: displayName,
        requiresAuth: serverInfo.requiresAuth,
        lastConnected: DateTime.now(),
      ),
    );

    // Update last connected time
    connection = connection.copyWith(
      lastConnected: DateTime.now(),
      displayName: displayName ?? connection.displayName,
      requiresAuth: serverInfo.requiresAuth,
    );

    // Update history
    _serverHistory.removeWhere((s) => s.url == serverInfo.url);
    _serverHistory.insert(0, connection);

    // Set as current server
    _currentServer = connection;

    // Persist changes
    await _saveState();

    notifyListeners();
    return connection;
  }

  /// Set the current server by ID
  Future<void> setCurrentServer(String serverId) async {
    final server = _serverHistory.firstWhere(
      (s) => s.id == serverId,
      orElse: () => throw StateError('Server not found: $serverId'),
    );

    _currentServer = server;
    await _storage.storeCurrentServerId(serverId);
    notifyListeners();
  }

  /// Remove a server from history
  Future<void> removeServer(String serverId) async {
    _serverHistory.removeWhere((s) => s.id == serverId);

    // Clear tokens for this server
    await _storage.clearTokens(serverId);

    // If this was the current server, clear it
    if (_currentServer?.id == serverId) {
      _currentServer = _serverHistory.isNotEmpty ? _serverHistory.first : null;
      await _storage.storeCurrentServerId(_currentServer?.id);
    }

    await _saveState();
    notifyListeners();
  }

  /// Update a server connection (e.g., after successful auth)
  Future<void> updateServer(ServerConnection server) async {
    final index = _serverHistory.indexWhere((s) => s.id == server.id);
    if (index >= 0) {
      _serverHistory[index] = server;
    } else {
      _serverHistory.insert(0, server);
    }

    if (_currentServer?.id == server.id) {
      _currentServer = server;
    }

    await _saveState();
    notifyListeners();
  }

  /// Clear all server history and tokens
  Future<void> clearAll() async {
    for (final server in _serverHistory) {
      await _storage.clearTokens(server.id);
    }

    _serverHistory.clear();
    _currentServer = null;

    await _storage.storeServerHistory([]);
    await _storage.storeCurrentServerId(null);

    notifyListeners();
  }

  /// Save current state to storage
  Future<void> _saveState() async {
    await _storage.storeServerHistory(
      _serverHistory.map((s) => s.toJson()).toList(),
    );
    await _storage.storeCurrentServerId(_currentServer?.id);
  }

  /// Get the base URL for API calls (from current server)
  String? get baseUrl => _currentServer?.url;

  /// Get auth headers if we have a token for the current server
  Future<Map<String, String>> getAuthHeaders() async {
    if (_currentServer == null) return {};

    final token = await _storage.getAccessToken(_currentServer!.id);
    if (token == null) return {};

    return {'Authorization': 'Bearer $token'};
  }

  @override
  void dispose() {
    _httpClient.close();
    super.dispose();
  }
}

// ============================================================================
// Riverpod Providers
// ============================================================================

/// Provider for secure storage service
final secureStorageProvider = Provider<SecureStorageService>((ref) {
  return SecureStorageFactory.create();
});

/// Provider for server config service
/// **DEPRECATED**: Use [serverRegistryProvider] and [appStateManagerProvider] instead.
@Deprecated('Use serverRegistryProvider and appStateManagerProvider instead')
final serverConfigProvider = ChangeNotifierProvider<ServerConfigService>((ref) {
  final storage = ref.watch(secureStorageProvider);
  return ServerConfigService(storage: storage);
});

/// Provider for current server ID only.
///
/// This provider only rebuilds when the server ID changes, not when
/// ServerConfigService notifies for other reasons (like metadata updates).
final currentServerIdProvider = Provider<String?>((ref) {
  return ref.watch(serverConfigProvider.select((c) => c.currentServer?.id));
});

/// Provider for current server connection.
///
/// Uses [currentServerIdProvider] to only rebuild when the server ID changes,
/// preventing unnecessary provider invalidation during auth token refresh
/// or other ServerConfigService notifications.
final currentServerProvider = Provider<ServerConnection?>((ref) {
  // Watch the ID to trigger rebuilds only on server change
  final serverId = ref.watch(currentServerIdProvider);
  if (serverId == null) return null;

  // Read the full server object (don't watch to avoid extra rebuilds)
  final config = ref.read(serverConfigProvider);
  return config.currentServer;
});

/// Provider for server history list
final serverHistoryProvider = Provider<List<ServerConnection>>((ref) {
  final config = ref.watch(serverConfigProvider);
  return config.serverHistory;
});
