// Web stub for notes service.
//
// Notes feature is not supported on web - the UI is hidden via kIsWeb check.
// These stubs exist to prevent compilation errors from dart:io imports.

/// Load notes data - not supported on web.
Future<String?> loadNotesData(String roomId) async {
  return null;
}

/// Save notes data - not supported on web.
Future<void> saveNotesData(String roomId, String data) async {
  // No-op on web
}

/// Check if notes feature is supported on this platform.
bool get isNotesSupported => false;
