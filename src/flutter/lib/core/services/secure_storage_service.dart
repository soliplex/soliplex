import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:soliplex/core/services/web_local_storage_stub.dart'
    if (dart.library.js_interop) 'web_local_storage_web.dart'
    as web_storage;
import 'package:soliplex/core/utils/debug_log.dart';

/// Abstract interface for secure credential storage
abstract class SecureStorageService {
  /// Write a value to secure storage
  Future<void> write(String key, String value);

  /// Read a value from secure storage
  Future<String?> read(String key);

  /// Delete a value from secure storage
  Future<void> delete(String key);

  /// Delete all values from secure storage
  Future<void> deleteAll();

  /// Check if a key exists
  Future<bool> containsKey(String key);

  /// Read all key-value pairs
  Future<Map<String, String>> readAll();
}

/// Storage keys for server authentication
class StorageKeys {
  StorageKeys._();
  static const String accessToken = 'access_token';
  static const String refreshToken = 'refresh_token';
  static const String tokenExpiry = 'token_expiry';
  static const String refreshExpiry = 'refresh_expiry';
  static const String currentServerId = 'current_server_id';
  static const String serverHistory = 'server_history';

  /// Get token key for a specific server
  static String serverAccessToken(String serverId) =>
      'server_${serverId}_access_token';
  static String serverRefreshToken(String serverId) =>
      'server_${serverId}_refresh_token';
  static String serverTokenExpiry(String serverId) =>
      'server_${serverId}_token_expiry';

  /// Get API key for a specific endpoint (completions endpoints)
  static String endpointApiKey(String endpointId) =>
      'endpoint_${endpointId}_api_key';
}

/// Native platform implementation using flutter_secure_storage
/// Falls back to in-memory storage if secure storage is unavailable
class NativeSecureStorageService implements SecureStorageService {
  NativeSecureStorageService()
    : _storage = const FlutterSecureStorage(
        aOptions: AndroidOptions(encryptedSharedPreferences: true),
        iOptions: IOSOptions(
          accessibility: KeychainAccessibility.first_unlock_this_device,
        ),
        mOptions: MacOsOptions(
          // Use unique account name to avoid keychain conflicts
          accountName: 'soliplex_server_config',
          accessibility: KeychainAccessibility.first_unlock_this_device,
        ),
      );
  final FlutterSecureStorage _storage;

  // Fallback storage when secure storage isn't available (e.g., unsigned macOS)
  final Map<String, String> _fallbackStorage = {};
  bool _useFallback = false;
  bool _checkedAvailability = false;

  Future<void> _checkAvailability() async {
    if (_checkedAvailability) return;
    _checkedAvailability = true;

    DebugLog.service('SecureStorage: Checking availability...');
    try {
      // Try a test write/read to check if secure storage works
      // Add timeout to prevent hanging on keychain issues
      DebugLog.service('SecureStorage: Testing write...');
      await _storage
          .write(key: '_test_key', value: 'test')
          .timeout(
            const Duration(seconds: 5),
            onTimeout: () {
              throw TimeoutException('Secure storage write timed out');
            },
          );
      DebugLog.service('SecureStorage: Testing delete...');
      await _storage
          .delete(key: '_test_key')
          .timeout(
            const Duration(seconds: 5),
            onTimeout: () {
              throw TimeoutException('Secure storage delete timed out');
            },
          );
      _useFallback = false;
      DebugLog.service('SecureStorage: Using native secure storage');
    } on Object catch (e) {
      DebugLog.warn('SecureStorage: Falling back to in-memory storage: $e');
      DebugLog.warn(
        'SecureStorage: For production, enable code signing in Xcode',
      );
      _useFallback = true;
    }
  }

  @override
  Future<void> write(String key, String value) async {
    await _checkAvailability();
    if (_useFallback) {
      _fallbackStorage[key] = value;
      return;
    }
    try {
      // Delete first to avoid macOS Keychain duplicate item error (-25299)
      try {
        await _storage.delete(key: key);
      } on Object catch (_) {
        // Ignore - key may not exist
      }
      await _storage.write(key: key, value: value);
    } on Object catch (e) {
      DebugLog.warn('SecureStorage: Write failed for $key: $e, using fallback');
      _fallbackStorage[key] = value;
    }
  }

  @override
  Future<String?> read(String key) async {
    await _checkAvailability();
    if (_useFallback) {
      return _fallbackStorage[key];
    }
    try {
      return await _storage.read(key: key);
    } on Object {
      return _fallbackStorage[key];
    }
  }

  @override
  Future<void> delete(String key) async {
    await _checkAvailability();
    _fallbackStorage.remove(key);
    if (_useFallback) return;
    try {
      await _storage.delete(key: key);
    } on Object {
      // Already removed from fallback
    }
  }

  @override
  Future<void> deleteAll() async {
    await _checkAvailability();
    _fallbackStorage.clear();
    if (_useFallback) return;
    try {
      await _storage.deleteAll();
    } on Object {
      // Already cleared fallback
    }
  }

  @override
  Future<bool> containsKey(String key) async {
    await _checkAvailability();
    if (_useFallback) {
      return _fallbackStorage.containsKey(key);
    }
    try {
      return await _storage.containsKey(key: key);
    } on Object {
      return _fallbackStorage.containsKey(key);
    }
  }

  @override
  Future<Map<String, String>> readAll() async {
    await _checkAvailability();
    if (_useFallback) {
      return Map.from(_fallbackStorage);
    }
    try {
      return await _storage.readAll();
    } on Object {
      return Map.from(_fallbackStorage);
    }
  }
}

/// Web implementation using localStorage for persistence.
///
/// Tokens persist across page refreshes. Uses window.localStorage
/// via conditional imports.
class WebSecureStorageService implements SecureStorageService {
  WebSecureStorageService() {
    _loadFromLocalStorage();
  }
  // In-memory cache to reduce localStorage reads
  final Map<String, String> _cache = {};
  bool _initialized = false;

  void _loadFromLocalStorage() {
    if (_initialized) return;
    _initialized = true;

    // Load all existing keys into cache
    final stored = web_storage.webLocalStorageReadAll();
    _cache.addAll(stored);
    DebugLog.service(
      'WebSecureStorageService: Loaded ${_cache.length} keys from localStorage',
    );
  }

  @override
  Future<void> write(String key, String value) async {
    _cache[key] = value;
    web_storage.webLocalStorageWrite(key, value);
  }

  @override
  Future<String?> read(String key) async {
    // Check cache first
    if (_cache.containsKey(key)) {
      return _cache[key];
    }
    // Fallback to localStorage (in case another tab wrote it)
    final value = web_storage.webLocalStorageRead(key);
    if (value != null) {
      _cache[key] = value;
    }
    return value;
  }

  @override
  Future<void> delete(String key) async {
    _cache.remove(key);
    web_storage.webLocalStorageDelete(key);
  }

  @override
  Future<void> deleteAll() async {
    _cache.clear();
    web_storage.webLocalStorageClear();
  }

  @override
  Future<bool> containsKey(String key) async {
    if (_cache.containsKey(key)) return true;
    return web_storage.webLocalStorageContainsKey(key);
  }

  @override
  Future<Map<String, String>> readAll() async {
    // Refresh cache from localStorage
    final stored = web_storage.webLocalStorageReadAll();
    _cache.addAll(stored);
    return Map.from(_cache);
  }
}

/// Factory to create the appropriate storage service for the platform
class SecureStorageFactory {
  static SecureStorageService create() {
    if (kIsWeb) {
      return WebSecureStorageService();
    }
    return NativeSecureStorageService();
  }
}

/// Extension methods for common token operations
extension TokenStorageExtension on SecureStorageService {
  /// Store tokens for a server
  Future<void> storeTokens({
    required String serverId,
    required String accessToken,
    String? refreshToken,
    DateTime? expiresAt,
    DateTime? refreshExpiresAt,
  }) async {
    await write(StorageKeys.serverAccessToken(serverId), accessToken);

    if (refreshToken != null) {
      await write(StorageKeys.serverRefreshToken(serverId), refreshToken);
    }

    if (expiresAt != null) {
      await write(
        StorageKeys.serverTokenExpiry(serverId),
        expiresAt.toIso8601String(),
      );
    }
  }

  /// Get access token for a server
  Future<String?> getAccessToken(String serverId) async {
    return read(StorageKeys.serverAccessToken(serverId));
  }

  /// Get refresh token for a server
  Future<String?> getRefreshToken(String serverId) async {
    return read(StorageKeys.serverRefreshToken(serverId));
  }

  /// Get token expiry for a server
  Future<DateTime?> getTokenExpiry(String serverId) async {
    final expiry = await read(StorageKeys.serverTokenExpiry(serverId));
    if (expiry == null) return null;
    return DateTime.tryParse(expiry);
  }

  /// Clear tokens for a server
  Future<void> clearTokens(String serverId) async {
    await delete(StorageKeys.serverAccessToken(serverId));
    await delete(StorageKeys.serverRefreshToken(serverId));
    await delete(StorageKeys.serverTokenExpiry(serverId));
  }

  /// Store server history (list of ServerConnection as JSON)
  Future<void> storeServerHistory(List<Map<String, dynamic>> history) async {
    await write(StorageKeys.serverHistory, jsonEncode(history));
  }

  /// Load server history
  Future<List<Map<String, dynamic>>> loadServerHistory() async {
    final data = await read(StorageKeys.serverHistory);
    if (data == null) return [];
    try {
      final list = jsonDecode(data) as List;
      return list.cast<Map<String, dynamic>>();
    } on Object {
      return [];
    }
  }

  /// Store current server ID
  Future<void> storeCurrentServerId(String? serverId) async {
    if (serverId == null) {
      await delete(StorageKeys.currentServerId);
    } else {
      await write(StorageKeys.currentServerId, serverId);
    }
  }

  /// Get current server ID
  Future<String?> getCurrentServerId() async {
    return read(StorageKeys.currentServerId);
  }

  // ===========================================================================
  // API Key Storage (for Completions endpoints)
  // ===========================================================================

  /// Store API key for a completions endpoint
  Future<void> storeApiKey({
    required String endpointId,
    required String apiKey,
  }) async {
    await write(StorageKeys.endpointApiKey(endpointId), apiKey);
  }

  /// Get API key for a completions endpoint
  Future<String?> getApiKey(String endpointId) async {
    return read(StorageKeys.endpointApiKey(endpointId));
  }

  /// Check if an endpoint has an API key stored
  Future<bool> hasApiKey(String endpointId) async {
    return containsKey(StorageKeys.endpointApiKey(endpointId));
  }

  /// Delete API key for an endpoint
  Future<void> deleteApiKey(String endpointId) async {
    await delete(StorageKeys.endpointApiKey(endpointId));
  }
}

// =============================================================================
// Provider
// =============================================================================

/// Provider for SecureStorageService.
/// Singleton - persists for app lifetime.
final secureStorageProvider = Provider<SecureStorageService>((ref) {
  return SecureStorageFactory.create();
});
