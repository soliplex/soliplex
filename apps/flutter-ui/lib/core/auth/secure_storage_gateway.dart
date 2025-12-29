import 'package:soliplex/core/auth/secure_storage_capabilities.dart';
import 'package:soliplex/core/services/secure_storage_service.dart';

/// Adapter that wraps SecureStorageService to implement the capability
/// interfaces
/// used by OIDC auth components.
///
/// This consolidates storage - both server config and OIDC tokens use the same
/// underlying SecureStorageService which has proper fallback support.
class SecureStorageGateway
    implements
        SecureStorageReadCapability,
        SecureStorageWriteCapability,
        SecureStorageDeleteCapability {
  SecureStorageGateway(this._storage);

  final SecureStorageService _storage;

  @override
  Future<String?> read(String key) async {
    return _storage.read(key);
  }

  @override
  Future<void> write(String key, String? value) async {
    if (value == null) {
      await _storage.delete(key);
    } else {
      await _storage.write(key, value);
    }
  }

  @override
  Future<void> delete(String key) async {
    await _storage.delete(key);
  }

  /// Clear all stored items
  Future<void> deleteAll() async {
    await _storage.deleteAll();
  }
}
