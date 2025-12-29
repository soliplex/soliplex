// ignore: avoid_web_libraries_in_flutter, deprecated_member_use (auto-documented)
import 'dart:html' as html;

/// Load feedback data from localStorage (web platform).
Future<String?> loadFeedbackData(String roomId) async {
  try {
    final key = 'soliplex_feedback_$roomId';
    return html.window.localStorage[key];
  } on Object {
    // Silently fail - will use in-memory only
    return null;
  }
}

/// Save feedback data to localStorage (web platform).
Future<void> saveFeedbackData(String roomId, String data) async {
  try {
    final key = 'soliplex_feedback_$roomId';
    html.window.localStorage[key] = data;
  } on Object {
    // Silently fail - data is still in memory
  }
}
