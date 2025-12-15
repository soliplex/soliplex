// ignore: one_member_abstracts (auto-documented)
abstract class SecureStorageReadCapability {
  Future<String?> read(String key);
}

// ignore: one_member_abstracts (auto-documented)
abstract class SecureStorageWriteCapability {
  Future<void> write(String key, String? value);
}

// ignore: one_member_abstracts (auto-documented)
abstract class SecureStorageDeleteCapability {
  Future<void> delete(String key);
}
