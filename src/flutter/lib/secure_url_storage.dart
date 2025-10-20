import 'dart:convert';

import 'secure_storage_gateway.dart';

class SecureUrlStorage {
  final _presetServiceUrlStorageKey = 'service.urls';
  final SecureStorageGateway _storage;

  SecureUrlStorage(this._storage);

  Future<void> addNewServiceUrl(String url) async {
    final savedUrlsJson = await _storage.read(_presetServiceUrlStorageKey);
    final savedUrls = jsonDecode(savedUrlsJson ?? '[]') as List<dynamic>;
    final savedUrlsSet = savedUrls.toSet();
    savedUrlsSet.add(url);
    await _storage.write(
      _presetServiceUrlStorageKey,
      jsonEncode(savedUrlsSet.toList()),
    );
  }

  Future<Set<String>> getServiceUrls() async {
    final savedUrlsJson = await _storage.read(_presetServiceUrlStorageKey);
    final savedUrls = jsonDecode(savedUrlsJson ?? '[]') as List<dynamic>;
    return savedUrls.map((e) => e.toString()).toSet();
  }

  Future<void> deleteUrl(String url) async {
    final savedUrlsJson = await _storage.read(_presetServiceUrlStorageKey);
    final savedUrls = jsonDecode(savedUrlsJson ?? '[]') as List<dynamic>;
    final savedUrlsSet = savedUrls.map((e) => e.toString()).toSet();
    if (savedUrlsSet.remove(url)) {
      await _storage.delete(_presetServiceUrlStorageKey);
    }
  }

  Future<void> deleteAllUrls() async {
    await _storage.delete(_presetServiceUrlStorageKey);
  }
}
