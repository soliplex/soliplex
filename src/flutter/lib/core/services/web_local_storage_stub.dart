// Stub implementation for non-web platforms.
//
// These functions are no-ops on non-web platforms.
// On web, the actual implementation in web_local_storage_web.dart is used.

/// Read a value from localStorage (stub returns null)
String? webLocalStorageRead(String key) => null;

void webLocalStorageWrite(String key, String value) {}

void webLocalStorageDelete(String key) {}

void webLocalStorageClear() {}

bool webLocalStorageContainsKey(String key) => false;

Map<String, String> webLocalStorageReadAll() => {};
