import 'package:flutter/foundation.dart';
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
    try {
      return await _storage.read(key: key);
    } catch (e) {
      debugPrint('SecureStorageGateway: Error reading $key: $e');
      return null;
    }
  }

  @override
  Future<void> write(String key, String? value) async {
    // Delete first to avoid macOS Keychain duplicate item error (-25299)
    try {
      debugPrint('SecureStorageGateway: Deleting $key before write');
      await _storage.delete(key: key);
    } catch (e) {
      debugPrint('SecureStorageGateway: Delete of $key failed (ok if not exists): $e');
    }

    try {
      debugPrint('SecureStorageGateway: Writing $key');
      await _storage.write(key: key, value: value);
      debugPrint('SecureStorageGateway: Write $key succeeded');
    } catch (e) {
      debugPrint('SecureStorageGateway: Write $key failed: $e');
      rethrow;
    }
  }

  @override
  Future<void> delete(String key) async {
    try {
      await _storage.delete(key: key);
    } catch (e) {
      debugPrint('SecureStorageGateway: Delete $key failed: $e');
    }
  }

  /// Clear all stored items
  Future<void> deleteAll() async {
    try {
      await _storage.deleteAll();
      debugPrint('SecureStorageGateway: Deleted all items');
    } catch (e) {
      debugPrint('SecureStorageGateway: DeleteAll failed: $e');
    }
  }
}
