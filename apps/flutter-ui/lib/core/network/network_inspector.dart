/// Network traffic inspector for capturing HTTP requests/responses.
///
/// This class is injected into HttpTransport to capture all network traffic
/// for debugging and diagnostics purposes.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex/core/network/network_inspector_models.dart';
import 'package:uuid/uuid.dart';

const _uuid = Uuid();

/// Callback type for recording requests.
typedef RequestRecorder =
    String Function({
      required String method,
      required Uri uri,
      required Map<String, String> headers,
      dynamic body,
    });

/// Callback type for recording responses.
typedef ResponseRecorder =
    void Function({
      required String requestId,
      required int statusCode,
      required Map<String, String> headers,
      dynamic body,
    });

/// Callback type for recording errors.
typedef ErrorRecorder =
    void Function({required String requestId, required String error});

/// Network inspector that captures HTTP traffic.
///
/// Usage in HttpTransport:
/// ```dart
/// // Before request
/// final requestId = inspector?.recordRequest(...);
///
/// // After response
/// inspector?.recordResponse(requestId: requestId, ...);
///
/// // On error
/// inspector?.recordError(requestId: requestId, error: e.toString());
/// ```
class NetworkInspector extends ChangeNotifier {
  NetworkInspector({this.maxEntries = 500});

  /// Maximum number of entries to keep in history.
  final int maxEntries;

  /// Internal storage of network entries.
  final List<NetworkEntry> _entries = [];

  /// Map for quick lookup by ID (for updating with response).
  final Map<String, int> _indexById = {};

  /// Stream controller for entry updates.
  final StreamController<NetworkEntry> _updateController =
      StreamController<NetworkEntry>.broadcast();

  /// All captured entries (newest first).
  List<NetworkEntry> get entries =>
      List.unmodifiable(_entries.reversed.toList());

  /// Stream of entry updates (new entries and modifications).
  Stream<NetworkEntry> get updates => _updateController.stream;

  /// Number of entries.
  int get entryCount => _entries.length;

  /// Record a new request and return its ID.
  ///
  /// Call this before making the HTTP request.
  String recordRequest({
    required String method,
    required Uri uri,
    required Map<String, String> headers,
    dynamic body,
  }) {
    final id = _uuid.v4();
    final entry = NetworkEntry.request(
      id: id,
      method: method,
      uri: uri,
      headers: headers,
      body: body,
    );

    _addEntry(entry);
    return id;
  }

  /// Record a response for a previously recorded request.
  ///
  /// Call this after receiving the HTTP response.
  void recordResponse({
    required String requestId,
    required int statusCode,
    required Map<String, String> headers,
    dynamic body,
  }) {
    final index = _indexById[requestId];
    if (index == null) return;

    final entry = _entries[index];
    final updated = entry.withResponse(
      statusCode: statusCode,
      headers: headers,
      body: body,
    );

    _entries[index] = updated;
    _updateController.add(updated);
    notifyListeners();
  }

  /// Record an error for a previously recorded request.
  ///
  /// Call this if the HTTP request fails.
  void recordError({required String requestId, required String error}) {
    final index = _indexById[requestId];
    if (index == null) return;

    final entry = _entries[index];
    final updated = entry.withError(error);

    _entries[index] = updated;
    _updateController.add(updated);
    notifyListeners();
  }

  /// Add a new entry and manage history size.
  void _addEntry(NetworkEntry entry) {
    // Evict oldest if at capacity
    while (_entries.length >= maxEntries) {
      final oldest = _entries.removeAt(0);
      _indexById.remove(oldest.id);
      // Reindex all entries
      _reindex();
    }

    _entries.add(entry);
    _indexById[entry.id] = _entries.length - 1;
    _updateController.add(entry);
    notifyListeners();
  }

  /// Rebuild the index map after removal.
  void _reindex() {
    _indexById.clear();
    for (var i = 0; i < _entries.length; i++) {
      _indexById[_entries[i].id] = i;
    }
  }

  /// Clear all entries.
  void clear() {
    _entries.clear();
    _indexById.clear();
    notifyListeners();
  }

  /// Get an entry by ID.
  NetworkEntry? getEntry(String id) {
    final index = _indexById[id];
    return index != null ? _entries[index] : null;
  }

  /// Filter entries by various criteria.
  List<NetworkEntry> filter({
    String? method,
    String? urlPattern,
    int? minStatusCode,
    int? maxStatusCode,
    bool? onlyErrors,
    bool? onlyInFlight,
  }) {
    return entries.where((entry) {
      if (method != null && entry.method != method) return false;
      if (urlPattern != null && !entry.fullUrl.contains(urlPattern)) {
        return false;
      }
      if (minStatusCode != null && (entry.statusCode ?? 0) < minStatusCode) {
        return false;
      }
      if (maxStatusCode != null && (entry.statusCode ?? 999) > maxStatusCode) {
        return false;
      }
      if ((onlyErrors ?? false) && !entry.isError) return false;
      if ((onlyInFlight ?? false) && !entry.isInFlight) return false;
      return true;
    }).toList();
  }

  @override
  void dispose() {
    _updateController.close();
    super.dispose();
  }
}

/// Global network inspector provider.
///
/// This is a singleton that persists for the app lifetime.
/// All HttpTransport instances share this inspector.
final networkInspectorProvider = ChangeNotifierProvider<NetworkInspector>((
  ref,
) {
  final inspector = NetworkInspector();
  ref.onDispose(inspector.dispose);
  return inspector;
});

/// Provider for filtered entries (convenience).
final networkEntriesProvider = Provider<List<NetworkEntry>>((ref) {
  final inspector = ref.watch(networkInspectorProvider);
  return inspector.entries;
});

/// Provider for entry count.
final networkEntryCountProvider = Provider<int>((ref) {
  final inspector = ref.watch(networkInspectorProvider);
  return inspector.entryCount;
});
