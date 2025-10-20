abstract class SecureStorageReadCapability {
  Future<String?> read(String key);
}

abstract class SecureStorageWriteCapability {
  Future<void> write(String key, String? value);
}

abstract class SecureStorageDeleteCapability {
  Future<void> delete(String key);
}
