import 'package:equatable/equatable.dart';

import 'package:soliplex/core/models/endpoint_models.dart';

/// OIDC authentication provider configuration
class OIDCAuthSystem extends Equatable {
  const OIDCAuthSystem({
    required this.id,
    required this.title,
    required this.serverUrl,
    required this.clientId,
    this.scope,
  });

  factory OIDCAuthSystem.fromJson(Map<String, dynamic> json) {
    return OIDCAuthSystem(
      id: json['id'] as String,
      title: json['title'] as String,
      serverUrl: json['server_url'] as String,
      clientId: json['client_id'] as String,
      scope: json['scope'] as String?,
    );
  }
  final String id;
  final String title;
  final String serverUrl;
  final String clientId;
  final String? scope;

  Map<String, dynamic> toJson() => {
    'id': id,
    'title': title,
    'server_url': serverUrl,
    'client_id': clientId,
    if (scope != null) 'scope': scope,
  };

  @override
  List<Object?> get props => [id, title, serverUrl, clientId, scope];
}

/// Result of probing a server for capabilities
class ServerInfo extends Equatable {
  const ServerInfo({
    required this.url,
    required this.isReachable,
    this.authDisabled = false,
    this.oidcProviders = const [],
    this.error,
    this.serverVersion,
  });

  factory ServerInfo.unreachable(String url, String error) {
    return ServerInfo(url: url, isReachable: false, error: error);
  }

  factory ServerInfo.fromProbe({
    required String url,
    required List<OIDCAuthSystem> providers,
    String? serverVersion,
  }) {
    return ServerInfo(
      url: url,
      isReachable: true,
      authDisabled: providers.isEmpty,
      oidcProviders: providers,
      serverVersion: serverVersion,
    );
  }
  final String url;
  final bool isReachable;
  final bool authDisabled;
  final List<OIDCAuthSystem> oidcProviders;
  final String? error;
  final String? serverVersion;

  /// Server requires authentication
  bool get requiresAuth => !authDisabled && oidcProviders.isNotEmpty;

  /// Server is ready to use without auth
  bool get isOpenAccess => isReachable && authDisabled;

  @override
  List<Object?> get props => [
    url,
    isReachable,
    authDisabled,
    oidcProviders,
    error,
    serverVersion,
  ];
}

/// A saved server connection with optional credentials
class ServerConnection extends Equatable {
  const ServerConnection({
    required this.id,
    required this.lastConnected,
    required this.config,
    this.tokenExpiry,
    this.authProviderId,
  });

  /// Legacy factory for creating AG-UI endpoints directly.
  factory ServerConnection.agUi({
    required String id,
    required String url,
    required DateTime lastConnected,
    String? displayName,
    bool requiresAuth = true,
    DateTime? tokenExpiry,
    String? authProviderId,
  }) {
    return ServerConnection(
      id: id,
      lastConnected: lastConnected,
      tokenExpiry: tokenExpiry,
      authProviderId: authProviderId,
      config: AgUiEndpoint(
        url: url,
        label: displayName ?? Uri.parse(url).host,
        requiresAuth: requiresAuth,
      ),
    );
  }

  factory ServerConnection.fromJson(Map<String, dynamic> json) {
    // Handle legacy JSON structure
    if (json['config'] == null) {
      return ServerConnection(
        id: json['id'] as String,
        lastConnected: DateTime.parse(json['last_connected'] as String),
        tokenExpiry: json['token_expiry'] != null
            ? DateTime.parse(json['token_expiry'] as String)
            : null,
        authProviderId: json['auth_provider_id'] as String?,
        config: AgUiEndpoint(
          url: json['url'] as String,
          label: json['display_name'] as String? ?? 'AG-UI Server',
          requiresAuth: json['requires_auth'] as bool? ?? false,
        ),
      );
    }

    return ServerConnection(
      id: json['id'] as String,
      lastConnected: DateTime.parse(json['last_connected'] as String),
      tokenExpiry: json['token_expiry'] != null
          ? DateTime.parse(json['token_expiry'] as String)
          : null,
      authProviderId: json['auth_provider_id'] as String?,
      config: EndpointConfiguration.fromJson(
        json['config'] as Map<String, dynamic>,
      ),
    );
  }
  final String id;
  final DateTime lastConnected;
  final DateTime? tokenExpiry;
  final String? authProviderId;

  /// The configuration for this endpoint.
  final EndpointConfiguration config;

  // Deprecated fields mapped to config for compatibility
  String get url => config.url;
  String get label => config.label;
  String? get displayName => config.label; // Alias for backward compat

  bool get requiresAuth {
    if (config is AgUiEndpoint) {
      return (config as AgUiEndpoint).requiresAuth;
    }
    return false;
  }

  /// Whether token has expired (if we have expiry info)
  bool get isTokenExpired {
    if (tokenExpiry == null) return false;
    return DateTime.now().isAfter(tokenExpiry!);
  }

  /// Whether token is expiring soon (within 5 minutes)
  bool get isTokenExpiringSoon {
    if (tokenExpiry == null) return false;
    return DateTime.now().isAfter(
      tokenExpiry!.subtract(const Duration(minutes: 5)),
    );
  }

  ServerConnection copyWith({
    String? id,
    DateTime? lastConnected,
    DateTime? tokenExpiry,
    String? authProviderId,
    EndpointConfiguration? config,
    // Legacy support for copyWith
    String? url,
    String? displayName,
    bool? requiresAuth,
  }) {
    // If legacy fields are provided, update config if it's AgUiEndpoint
    var newConfig = config ?? this.config;
    if (newConfig is AgUiEndpoint &&
        (url != null || displayName != null || requiresAuth != null)) {
      newConfig = AgUiEndpoint(
        url: url ?? newConfig.url,
        label: displayName ?? newConfig.label,
        requiresAuth: requiresAuth ?? newConfig.requiresAuth,
      );
    }

    return ServerConnection(
      id: id ?? this.id,
      lastConnected: lastConnected ?? this.lastConnected,
      tokenExpiry: tokenExpiry ?? this.tokenExpiry,
      authProviderId: authProviderId ?? this.authProviderId,
      config: newConfig,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'last_connected': lastConnected.toIso8601String(),
    if (tokenExpiry != null) 'token_expiry': tokenExpiry!.toIso8601String(),
    if (authProviderId != null) 'auth_provider_id': authProviderId,
    'config': config.toJson(),
    // Keep legacy fields for a while? Or just break it?
    // Breaking it is fine if we migrate on load.
    // But if we want backward compatibility with older app versions sharing
    // storage...
    // Let's rely on 'config' being the source of truth.
  };

  @override
  List<Object?> get props => [
    id,
    lastConnected,
    tokenExpiry,
    authProviderId,
    config,
  ];
}

/// Authentication state for the current session
enum AuthStatus {
  /// No server configured
  noServer,

  /// Server configured but not authenticated
  unauthenticated,

  /// Authentication in progress
  authenticating,

  /// Authenticated and ready
  authenticated,

  /// Token expired, needs refresh or re-auth
  tokenExpired,

  /// Authentication failed
  error,
}

class AuthState extends Equatable {
  const AuthState({
    this.status = AuthStatus.noServer,
    this.currentServer,
    this.userId,
    this.userName,
    this.userEmail,
    this.error,
  });

  const AuthState.initial() : this();
  final AuthStatus status;
  final ServerConnection? currentServer;
  final String? userId;
  final String? userName;
  final String? userEmail;
  final String? error;

  bool get isAuthenticated => status == AuthStatus.authenticated;
  bool get needsAuth =>
      status == AuthStatus.unauthenticated || status == AuthStatus.tokenExpired;
  bool get hasServer => currentServer != null;

  AuthState copyWith({
    AuthStatus? status,
    ServerConnection? currentServer,
    String? userId,
    String? userName,
    String? userEmail,
    String? error,
    bool clearServer = false,
    bool clearUser = false,
    bool clearError = false,
  }) {
    return AuthState(
      status: status ?? this.status,
      currentServer: clearServer ? null : (currentServer ?? this.currentServer),
      userId: clearUser ? null : (userId ?? this.userId),
      userName: clearUser ? null : (userName ?? this.userName),
      userEmail: clearUser ? null : (userEmail ?? this.userEmail),
      error: clearError ? null : (error ?? this.error),
    );
  }

  @override
  List<Object?> get props => [
    status,
    currentServer,
    userId,
    userName,
    userEmail,
    error,
  ];
}

/// Token data (for internal use, not persisted directly)
class TokenData {
  const TokenData({
    required this.accessToken,
    this.refreshToken,
    this.expiresAt,
    this.refreshExpiresAt,
  });

  factory TokenData.fromCallbackParams(Map<String, String> params) {
    final now = DateTime.now();
    final expiresIn = params['expires_in'] != null
        ? int.tryParse(params['expires_in']!)
        : null;
    final refreshExpiresIn = params['refresh_expires_in'] != null
        ? int.tryParse(params['refresh_expires_in']!)
        : null;

    return TokenData(
      accessToken: params['token'] ?? params['access_token'] ?? '',
      refreshToken: params['refresh_token'],
      expiresAt: expiresIn != null
          ? now.add(Duration(seconds: expiresIn))
          : null,
      refreshExpiresAt: refreshExpiresIn != null
          ? now.add(Duration(seconds: refreshExpiresIn))
          : null,
    );
  }
  final String accessToken;
  final String? refreshToken;
  final DateTime? expiresAt;
  final DateTime? refreshExpiresAt;

  bool get isExpired {
    if (expiresAt == null) return false;
    return DateTime.now().isAfter(expiresAt!);
  }

  bool get isExpiringSoon {
    if (expiresAt == null) return false;
    return DateTime.now().isAfter(
      expiresAt!.subtract(const Duration(minutes: 5)),
    );
  }

  bool get canRefresh {
    if (refreshToken == null) return false;
    if (refreshExpiresAt == null) return true;
    return DateTime.now().isBefore(refreshExpiresAt!);
  }
}
