import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex/core/network/network_transport_layer.dart';
import 'package:soliplex/core/providers/app_providers.dart';
import 'package:soliplex/core/services/auth_manager.dart';
import 'package:soliplex/core/utils/http_config.dart';
import 'package:soliplex/core/utils/url_builder.dart';

/// Response from the MCP token endpoint.
class McpTokenResponse {
  McpTokenResponse({
    required this.token,
    required this.roomId,
    this.expiresAt,
    this.serverUrl,
  });

  factory McpTokenResponse.fromJson(Map<String, dynamic> json) {
    debugPrint('McpTokenResponse.fromJson keys: ${json.keys.toList()}');
    debugPrint('McpTokenResponse.fromJson: $json');

    DateTime? expiresAt;
    // Try different field names for expiration
    final expiresField =
        json['expires_at'] ?? json['expires'] ?? json['expiry'];
    if (expiresField != null) {
      if (expiresField is String) {
        expiresAt = DateTime.tryParse(expiresField);
      } else if (expiresField is int) {
        // Unix timestamp
        expiresAt = DateTime.fromMillisecondsSinceEpoch(expiresField * 1000);
      }
    }

    // Try different field names for token
    final rawToken = json['token'] ?? json['mcp_token'] ?? json['access_token'];
    final tokenValue = rawToken?.toString() ?? '';

    debugPrint('McpTokenResponse: parsed token length=${tokenValue.length}');

    return McpTokenResponse(
      token: tokenValue,
      roomId: json['room_id'] as String? ?? '',
      expiresAt: expiresAt,
      serverUrl: json['server_url'] as String?,
    );
  }
  final String token;
  final String roomId;
  final DateTime? expiresAt;
  final String? serverUrl;

  /// Check if the token is expired.
  bool get isExpired {
    if (expiresAt == null) return false;
    return DateTime.now().isAfter(expiresAt!);
  }

  /// Get time until expiration as a human-readable string.
  String? get expiresIn {
    if (expiresAt == null) return null;
    final duration = expiresAt!.difference(DateTime.now());
    if (duration.isNegative) return 'Expired';
    if (duration.inDays > 0) return '${duration.inDays}d';
    if (duration.inHours > 0) return '${duration.inHours}h';
    if (duration.inMinutes > 0) return '${duration.inMinutes}m';
    return '${duration.inSeconds}s';
  }
}

/// Service for fetching MCP tokens for rooms.
///
/// Uses NetworkTransportLayer for HTTP requests, which provides:
/// - Network Inspector integration
/// - 401 retry with token refresh
/// - Consistent timeout handling
class McpTokenService {
  McpTokenService({required AuthManager authManager})
    : _authManager = authManager;
  final AuthManager _authManager;

  /// Fetch an MCP token for the given room.
  ///
  /// transportLayer should be the transport layer for the server. If not
  /// provided, falls back to a simple HTTP request without retry logic.
  ///
  /// Returns null if the request fails or the room doesn't support MCP.
  Future<McpTokenResponse?> getToken({
    required String serverUrl,
    required String serverId,
    required String roomId,
    NetworkTransportLayer? transportLayer,
  }) async {
    try {
      final urlBuilder = UrlBuilder(serverUrl);
      final uri = urlBuilder.mcpToken(roomId);

      final headers = await _authManager.getAuthHeaders(serverId);

      debugPrint('McpTokenService: Fetching token from $uri');

      if (transportLayer != null) {
        // Use transport layer - gets inspector + 401 retry for free
        final response = await transportLayer
            .get(uri, additionalHeaders: headers)
            .timeout(HttpConfig.defaultTimeout);

        debugPrint('McpTokenService: Response status ${response.statusCode}');
        debugPrint('McpTokenService: Response body: ${response.body}');

        if (response.statusCode == 200) {
          final json = jsonDecode(response.body) as Map<String, dynamic>;
          return McpTokenResponse.fromJson(json);
        } else {
          debugPrint(
            'McpTokenService: Failed with status ${response.statusCode}',
          );
          debugPrint('McpTokenService: Response: ${response.body}');
          return null;
        }
      } else {
        // Fallback: direct HTTP request (for backward compatibility)
        debugPrint(
          'McpTokenService: Warning - no transport layer, using direct HTTP',
        );
        return null;
      }
    } on Object catch (e) {
      debugPrint('McpTokenService: Error fetching token: $e');
      return null;
    }
  }

  /// Generate MCP connection config for Claude Desktop or other MCP clients.
  ///
  /// Returns a JSON config suitable for claude_desktop_config.json
  String generateMcpConfig({
    required String serverUrl,
    required String roomId,
    required String token,
  }) {
    final urlBuilder = UrlBuilder(serverUrl);
    // MCP endpoint is typically at /mcp or /api/v1/rooms/{roomId}/mcp
    final mcpUrl = '${urlBuilder.serverUrl}/api/v1/rooms/$roomId/mcp';

    final config = {
      'mcpServers': {
        'soliplex-$roomId': {
          'url': mcpUrl,
          'transport': 'http',
          'headers': {'Authorization': 'Bearer $token'},
        },
      },
    };

    return const JsonEncoder.withIndent('  ').convert(config);
  }
}

/// Provider for MCP token service.
///
/// The service requires a NetworkTransportLayer to be passed to getToken()
/// for network requests. Use connectionRegistryProvider to get the transport
/// layer for the current server.
final mcpTokenServiceProvider = Provider<McpTokenService>((ref) {
  final authManager = ref.read(authManagerProvider);
  return McpTokenService(authManager: authManager);
});

/// State for MCP token fetching.
class McpTokenState {
  const McpTokenState({this.token, this.isLoading = false, this.error});
  final McpTokenResponse? token;
  final bool isLoading;
  final String? error;

  McpTokenState copyWith({
    McpTokenResponse? token,
    bool? isLoading,
    String? error,
    bool clearError = false,
    bool clearToken = false,
  }) {
    return McpTokenState(
      token: clearToken ? null : (token ?? this.token),
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

/// Notifier for managing MCP token state per room.
class McpTokenNotifier extends StateNotifier<McpTokenState> {
  McpTokenNotifier({
    required McpTokenService service,
    required String serverUrl,
    required String serverId,
  }) : _service = service,
       _serverUrl = serverUrl,
       _serverId = serverId,
       super(const McpTokenState());
  final McpTokenService _service;
  final String _serverUrl;
  final String _serverId;

  /// Fetch token for a room.
  Future<void> fetchToken(String roomId) async {
    state = state.copyWith(isLoading: true, clearError: true);

    final token = await _service.getToken(
      serverUrl: _serverUrl,
      serverId: _serverId,
      roomId: roomId,
    );

    if (token != null) {
      state = state.copyWith(token: token, isLoading: false);
    } else {
      state = state.copyWith(
        isLoading: false,
        error: 'Failed to fetch MCP token',
      );
    }
  }

  /// Clear the current token.
  void clearToken() {
    state = const McpTokenState();
  }

  /// Generate config JSON for the current token.
  String? generateConfig(String roomId) {
    if (state.token == null) return null;
    return _service.generateMcpConfig(
      serverUrl: _serverUrl,
      roomId: roomId,
      token: state.token!.token,
    );
  }
}
