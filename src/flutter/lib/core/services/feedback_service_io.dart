// reason: io required for native platform
// ignore_for_file: avoid_slow_async_io
import 'dart:io';

import 'package:path_provider/path_provider.dart';

/// Load feedback data from file system (native platforms).
Future<String?> loadFeedbackData(String roomId) async {
  try {
    final file = await _getFeedbackFile(roomId);
    if (await file.exists()) {
      return await file.readAsString();
    }
  } on Object {
    // Silently fail - will use in-memory only
  }
  return null;
}

/// Save feedback data to file system (native platforms).
Future<void> saveFeedbackData(String roomId, String data) async {
  try {
    final file = await _getFeedbackFile(roomId);
    await file.writeAsString(data);
  } on Object {
    // Silently fail - data is still in memory
  }
}

/// Get the feedback file for a room.
Future<File> _getFeedbackFile(String roomId) async {
  final directory = await getApplicationDocumentsDirectory();
  final feedbackDir = Directory('${directory.path}/soliplex_feedback');

  if (!await feedbackDir.exists()) {
    await feedbackDir.create(recursive: true);
  }

  return File('${feedbackDir.path}/$roomId.json');
}
