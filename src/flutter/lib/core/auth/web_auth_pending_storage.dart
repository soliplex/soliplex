import 'dart:convert';

import 'package:soliplex/core/services/secure_storage_service.dart';
import 'package:soliplex/core/utils/debug_log.dart';

/// Data stored between OIDC redirect and callback.
///
/// When the browser redirects to the OIDC provider, this data is persisted
/// so it can be retrieved when the callback returns (potentially in a
/// different app instance after page reload).
class PendingWebAuth {
  const PendingWebAuth({
    required this.serverId,
    required this.providerId,
    required this.codeVerifier,
    required this.state,
    required this.tokenEndpoint,
    required this.clientId,
    required this.redirectUrl,
    required this.createdAt,
  });

  factory PendingWebAuth.fromJson(Map<String, dynamic> json) {
    return PendingWebAuth(
      serverId: json['serverId'] as String,
      providerId: json['providerId'] as String,
      codeVerifier: json['codeVerifier'] as String,
      state: json['state'] as String,
      tokenEndpoint: json['tokenEndpoint'] as String,
      clientId: json['clientId'] as String,
      redirectUrl: json['redirectUrl'] as String,
      createdAt: DateTime.parse(json['createdAt'] as String),
    );
  }

  /// The server we're authenticating to
  final String serverId;

  /// The OIDC provider ID
  final String providerId;

  /// PKCE code verifier (kept secret, used in token exchange)
  final String codeVerifier;

  /// State parameter for CSRF protection
  final String state;

  /// Token endpoint URL for code exchange
  final String tokenEndpoint;

  /// OAuth client ID
  final String clientId;

  /// Redirect URL registered with the provider
  final String redirectUrl;

  /// When the auth flow started (for expiry)
  final DateTime createdAt;

  /// Maximum age for pending auth data (5 minutes)
  static const maxAge = Duration(minutes: 5);

  /// Check if this pending auth has expired
  bool get isExpired => DateTime.now().difference(createdAt) > maxAge;

  Map<String, dynamic> toJson() => {
    'serverId': serverId,
    'providerId': providerId,
    'codeVerifier': codeVerifier,
    'state': state,
    'tokenEndpoint': tokenEndpoint,
    'clientId': clientId,
    'redirectUrl': redirectUrl,
    'createdAt': createdAt.toIso8601String(),
  };

  @override
  String toString() =>
      // ignore: lines_longer_than_80_chars (auto-documented)
      'PendingWebAuth(serverId: $serverId, provider: $providerId, state: ${state.substring(0, 8)}...)';
}

/// Storage for pending web authentication state.
///
/// Persists auth context between the initial redirect and the callback.
/// Uses SecureStorageService for persistence (localStorage on web).
class WebAuthPendingStorage {
  WebAuthPendingStorage(this._storage);
  final SecureStorageService _storage;

  static const _storageKey = 'pending_web_auth';

  /// Save pending auth data before redirecting to OIDC provider
  Future<void> savePendingAuth(PendingWebAuth pending) async {
    final json = jsonEncode(pending.toJson());
    await _storage.write(_storageKey, json);
    DebugLog.auth(
      'WebAuthPendingStorage: Saved pending auth for ${pending.serverId}',
    );
  }

  /// Retrieve pending auth data after callback
  ///
  /// Returns null if no pending auth exists or if it has expired.
  Future<PendingWebAuth?> getPendingAuth() async {
    final json = await _storage.read(_storageKey);
    if (json == null) {
      DebugLog.auth('WebAuthPendingStorage: No pending auth found');
      return null;
    }

    try {
      final data = jsonDecode(json) as Map<String, dynamic>;
      final pending = PendingWebAuth.fromJson(data);

      if (pending.isExpired) {
        DebugLog.warn(
          'WebAuthPendingStorage: Pending auth expired '
          '(created ${pending.createdAt}, max age ${PendingWebAuth.maxAge})',
        );
        await clearPendingAuth();
        return null;
      }

      DebugLog.auth(
        'WebAuthPendingStorage: Retrieved pending auth for ${pending.serverId}',
      );
      return pending;
    } on Object catch (e) {
      DebugLog.error('WebAuthPendingStorage: Failed to parse pending auth: $e');
      await clearPendingAuth();
      return null;
    }
  }

  /// Clear pending auth data after successful exchange or error
  Future<void> clearPendingAuth() async {
    await _storage.delete(_storageKey);
    DebugLog.auth('WebAuthPendingStorage: Cleared pending auth');
  }

  /// Check if there is valid (non-expired) pending auth
  Future<bool> hasPendingAuth() async {
    final pending = await getPendingAuth();
    return pending != null;
  }

  /// Validate that the returned state matches the stored state (CSRF
  /// protection)
  Future<bool> validateState(String returnedState) async {
    final pending = await getPendingAuth();
    if (pending == null) {
      DebugLog.warn(
        'WebAuthPendingStorage: Cannot validate state - no pending auth',
      );
      return false;
    }

    final isValid = pending.state == returnedState;
    if (!isValid) {
      DebugLog.warn(
        'WebAuthPendingStorage: State mismatch! '
        'Expected: ${pending.state.substring(0, 8)}..., '
        'Got: ${returnedState.substring(0, 8)}...',
      );
    }
    return isValid;
  }
}
