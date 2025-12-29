import 'package:web/web.dart' as web;

/// Web implementation using window.localStorage.
///
/// Provides persistent storage that survives page refreshes.

String? webLocalStorageRead(String key) {
  return web.window.localStorage.getItem(key);
}

void webLocalStorageWrite(String key, String value) {
  web.window.localStorage.setItem(key, value);
}

void webLocalStorageDelete(String key) {
  web.window.localStorage.removeItem(key);
}

void webLocalStorageClear() {
  // Only clear keys with our prefix to avoid removing other app data
  final keysToRemove = <String>[];
  for (var i = 0; i < web.window.localStorage.length; i++) {
    final key = web.window.localStorage.key(i);
    if (key != null) {
      keysToRemove.add(key);
    }
  }
  // ignore: prefer_foreach (tear-offs disallowed for interop)
  for (final key in keysToRemove) {
    web.window.localStorage.removeItem(key);
  }
}

bool webLocalStorageContainsKey(String key) {
  return web.window.localStorage.getItem(key) != null;
}

Map<String, String> webLocalStorageReadAll() {
  final result = <String, String>{};
  for (var i = 0; i < web.window.localStorage.length; i++) {
    final key = web.window.localStorage.key(i);
    if (key != null) {
      final value = web.window.localStorage.getItem(key);
      if (value != null) {
        result[key] = value;
      }
    }
  }
  return result;
}
