import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'secure_storage_capabilities.dart';

class SecureStorageGateway
    implements
        SecureStorageReadCapability,
        SecureStorageWriteCapability,
        SecureStorageDeleteCapability {
  const SecureStorageGateway(this._storage);

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read(String key) async {
    return await _storage.read(key: key);
  }

  @override
  Future<void> write(String key, String? value) async {
    // Delete first to avoid macOS Keychain duplicate item error (-25299)
    try {
      await _storage.delete(key: key);
    } catch (_) {
      // Ignore delete errors - key may not exist
    }
    await _storage.write(key: key, value: value);
  }

  @override
  Future<void> delete(String key) async {
    await _storage.delete(key: key);
  }
}
