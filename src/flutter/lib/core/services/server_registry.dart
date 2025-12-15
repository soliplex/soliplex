import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:soliplex/core/models/endpoint_models.dart';
import 'package:soliplex/core/models/server_models.dart';
import 'package:soliplex/core/network/network_inspector.dart';
import 'package:soliplex/core/services/secure_storage_service.dart';
import 'package:soliplex/core/utils/debug_log.dart';
import 'package:soliplex/core/utils/http_config.dart';
import 'package:soliplex/core/utils/url_builder.dart';
import 'package:uuid/uuid.dart';

/// Registry for server connections.
///
/// Plain class (no ChangeNotifier) for server storage and discovery.
/// Methods return data directly, no notifications.
///
/// Optionally accepts NetworkInspector for traffic observability.
/// HTTP calls (server probing) are instrumented to appear in the Network
/// Inspector panel.
class ServerRegistry {
  ServerRegistry({
    SecureStorageService? storage,
    http.Client? httpClient,
    NetworkInspector? inspector,
  }) : _storage = storage ?? SecureStorageFactory.create(),
       _httpClient = httpClient ?? http.Client(),
       _inspector = inspector;
  final SecureStorageService _storage;
  final http.Client _httpClient;
  final NetworkInspector? _inspector;

  List<ServerConnection> _serverHistory = [];
  ServerConnection? _currentServer;
  bool _initialized = false;

  // Read-only accessors
  List<ServerConnection> get serverHistory => List.unmodifiable(_serverHistory);
  ServerConnection? get currentServer => _currentServer;
  bool get hasServer => _currentServer != null;
  bool get isInitialized => _initialized;

  /// Initialize the registry, loading saved state.
  Future<void> initialize() async {
    if (_initialized) return;
    DebugLog.service('ServerRegistry.initialize: Starting...');

    try {
      // Load server history
      DebugLog.service('ServerRegistry.initialize: Loading server history...');
      final historyJson = await _storage.loadServerHistory();
      DebugLog.service(
        'ServerRegistry.initialize: Loaded ${historyJson.length} servers',
      );
      _serverHistory = historyJson.map(ServerConnection.fromJson).toList();

      // Sort by last connected (most recent first)
      _serverHistory.sort((a, b) => b.lastConnected.compareTo(a.lastConnected));

      // Load current server ID
      final currentId = await _storage.getCurrentServerId();
      if (currentId != null) {
        _currentServer = _serverHistory.firstWhere(
          (s) => s.id == currentId,
          orElse: () => _serverHistory.isNotEmpty
              ? _serverHistory.first
              : throw StateError('No servers'),
        );
      }

      _initialized = true;
    } on Object catch (e) {
      DebugLog.error('ServerRegistry: Error loading state: $e');
      _initialized = true; // Mark initialized even on error
    }
  }

  /// Load the saved current server.
  /// Returns null if no server is saved.
  Future<ServerConnection?> loadSavedServer() async {
    if (!_initialized) await initialize();
    return _currentServer;
  }

  /// Normalize a server URL.
  String normalizeUrl(String url) {
    return UrlBuilder.normalizeBaseUrl(url);
  }

  /// Probe a server to discover its capabilities.
  Future<ServerInfo> probeServer(String url) async {
    final normalizedUrl = normalizeUrl(url);
    final urlBuilder = UrlBuilder(normalizedUrl);

    // Record request for Network Inspector
    final loginUrl = urlBuilder.login();
    final requestId = _inspector?.recordRequest(
      method: 'GET',
      uri: loginUrl,
      headers: const {},
    );

    try {
      // Try to fetch /api/login endpoint to discover OIDC providers
      final response = await _httpClient
          .get(loginUrl)
          .timeout(HttpConfig.probeTimeout);

      // Record response for Network Inspector
      if (requestId != null) {
        _inspector?.recordResponse(
          requestId: requestId,
          statusCode: response.statusCode,
          headers: response.headers,
          body: response.body,
        );
      }

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final providers = _parseOidcProviders(data);

        return ServerInfo.fromProbe(url: normalizedUrl, providers: providers);
      } else if (response.statusCode == 404) {
        // /login not found - try /rooms to verify it's a Soliplex server
        return await _probeRoomsEndpoint(normalizedUrl);
      } else {
        return ServerInfo.unreachable(
          normalizedUrl,
          'Server returned status ${response.statusCode}',
        );
      }
    } on TimeoutException {
      // Record error for Network Inspector
      if (requestId != null) {
        _inspector?.recordError(
          requestId: requestId,
          error: 'Connection timed out',
        );
      }
      return ServerInfo.unreachable(normalizedUrl, 'Connection timed out');
    } on Object catch (e) {
      // Record error for Network Inspector
      if (requestId != null) {
        _inspector?.recordError(requestId: requestId, error: e.toString());
      }
      return ServerInfo.unreachable(normalizedUrl, e.toString());
    }
  }

  Future<ServerInfo> _probeRoomsEndpoint(String url) async {
    final urlBuilder = UrlBuilder(url);
    final roomsUrl = urlBuilder.rooms();

    // Record request for Network Inspector
    final requestId = _inspector?.recordRequest(
      method: 'GET',
      uri: roomsUrl,
      headers: const {},
    );

    try {
      final response = await _httpClient
          .get(roomsUrl)
          .timeout(HttpConfig.probeTimeout);

      // Record response for Network Inspector
      if (requestId != null) {
        _inspector?.recordResponse(
          requestId: requestId,
          statusCode: response.statusCode,
          headers: response.headers,
          body: response.body,
        );
      }

      if (response.statusCode == 200) {
        return ServerInfo(url: url, isReachable: true, authDisabled: true);
      } else if (response.statusCode == 401) {
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
    } on Object catch (e) {
      // Record error for Network Inspector
      if (requestId != null) {
        _inspector?.recordError(requestId: requestId, error: e.toString());
      }
      return ServerInfo.unreachable(url, e.toString());
    }
  }

  List<OIDCAuthSystem> _parseOidcProviders(dynamic data) {
    final providers = <OIDCAuthSystem>[];

    if (data is Map<String, dynamic>) {
      data.forEach((key, value) {
        if (value is Map<String, dynamic>) {
          try {
            providers.add(OIDCAuthSystem.fromJson({'id': key, ...value}));
          } on Object catch (e) {
            DebugLog.error('Failed to parse OIDC provider $key: $e');
          }
        }
      });
    } else if (data is List) {
      for (final item in data) {
        if (item is Map<String, dynamic>) {
          try {
            providers.add(OIDCAuthSystem.fromJson(item));
          } on Object catch (e) {
            DebugLog.error('Failed to parse OIDC provider: $e');
          }
        }
      }
    }

    return providers;
  }

  /// Save a server connection.
  /// Returns the saved connection (may have updated ID/timestamps).
  Future<ServerConnection> saveServer(
    ServerInfo serverInfo, {
    String? displayName,
    EndpointConfiguration? config,
  }) async {
    if (!serverInfo.isReachable) {
      throw StateError('Cannot save unreachable server');
    }

    // Check if we already have this server in history
    var connection = _serverHistory.firstWhere(
      (s) => s.url == serverInfo.url,
      orElse: () => ServerConnection(
        id: const Uuid().v4(),
        lastConnected: DateTime.now(),
        config:
            config ??
            AgUiEndpoint(
              url: serverInfo.url,
              label: displayName ?? Uri.parse(serverInfo.url).host,
              requiresAuth: serverInfo.requiresAuth,
            ),
      ),
    );

    // Update last connected time and config
    connection = connection.copyWith(
      lastConnected: DateTime.now(),
      displayName: displayName ?? connection.displayName,
      requiresAuth: serverInfo.requiresAuth,
      config: config, // Update config if provided
    );

    // Update history
    _serverHistory.removeWhere((s) => s.url == serverInfo.url);
    _serverHistory.insert(0, connection);

    // Set as current server
    _currentServer = connection;

    // Persist changes
    await _saveState();

    return connection;
  }

  /// Update a server connection.
  Future<ServerConnection> updateServer(ServerConnection server) async {
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
    return server;
  }

  /// Set the current server by ID.
  Future<ServerConnection> setCurrentServer(String serverId) async {
    final server = _serverHistory.firstWhere(
      (s) => s.id == serverId,
      orElse: () => throw StateError('Server not found: $serverId'),
    );

    _currentServer = server;
    await _storage.storeCurrentServerId(serverId);
    return server;
  }

  /// Remove a server from history.
  Future<void> removeServer(String serverId) async {
    _serverHistory.removeWhere((s) => s.id == serverId);

    // Clear tokens for this server
    await _storage.clearTokens(serverId);

    // If this was the current server, switch to next
    if (_currentServer?.id == serverId) {
      _currentServer = _serverHistory.isNotEmpty ? _serverHistory.first : null;
      await _storage.storeCurrentServerId(_currentServer?.id);
    }

    await _saveState();
  }

  /// Clear all server history and tokens.
  Future<void> clearAll() async {
    for (final server in _serverHistory) {
      await _storage.clearTokens(server.id);
    }

    _serverHistory.clear();
    _currentServer = null;

    await _storage.storeServerHistory([]);
    await _storage.storeCurrentServerId(null);
  }

  Future<void> _saveState() async {
    await _storage.storeServerHistory(
      _serverHistory.map((s) => s.toJson()).toList(),
    );
    await _storage.storeCurrentServerId(_currentServer?.id);
  }

  void dispose() {
    _httpClient.close();
  }
}
