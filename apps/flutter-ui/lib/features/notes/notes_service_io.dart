// reason: io required for native platform
// ignore_for_file: avoid_slow_async_io
import 'dart:io';

import 'package:path_provider/path_provider.dart';

/// Load notes data from file system (native platforms).
Future<String?> loadNotesData(String roomId) async {
  try {
    final file = await _getNotesFile(roomId);
    if (await file.exists()) {
      return await file.readAsString();
    }
  } on Object {
    // Silently fail - will return null
  }
  return null;
}

/// Save notes data to file system (native platforms).
Future<void> saveNotesData(String roomId, String data) async {
  final file = await _getNotesFile(roomId);
  await file.writeAsString(data);
}

/// Get the notes file for a room.
Future<File> _getNotesFile(String roomId) async {
  final directory = await getApplicationDocumentsDirectory();
  final notesDir = Directory('${directory.path}/soliplex_notes');

  if (!await notesDir.exists()) {
    await notesDir.create(recursive: true);
  }

  return File('${notesDir.path}/$roomId.md');
}

/// Check if notes feature is supported on this platform.
bool get isNotesSupported => true;
