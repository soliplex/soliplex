/// Centralized debug logging utility.
///
/// Set enabled to false to disable all debug logging.
/// Set individual flags to enable specific categories.
library;

import 'package:flutter/foundation.dart';

class DebugLog {
  /// Master switch - set to false to disable all logging
  static bool enabled = true;

  /// Include timestamps in log output
  static bool includeTimestamps = true;

  /// Log categories - enable only what you need to debug
  static bool agUiEvents = true; // AG-UI event processing
  static bool chatMessages = true; // Chat message flow (critical for debugging)
  static bool messageMapping =
      true; // Message ID mapping (critical for second response issue)
  static bool toolsEnabled = false; // Tool execution
  static bool threadEnabled = true; // Thread/SSE stream processing
  static bool servicesEnabled =
      true; // Service initialization - ENABLED FOR DEBUG
  static bool canvasEnabled = false; // Canvas operations
  static bool networkEnabled = true; // Network/connection management
  static bool uiEnabled = false; // UI state changes
  static bool authEnabled = true; // Authentication flow

  /// Returns a timezone-aware timestamp string.
  /// Format: HH:mm:ss.SSS ±HHMM (e.g., "14:30:45.123 -0800")
  static String _timestamp() {
    if (!includeTimestamps) return '';
    final now = DateTime.now();
    final offset = now.timeZoneOffset;
    final sign = offset.isNegative ? '-' : '+';
    final hours = offset.inHours.abs().toString().padLeft(2, '0');
    final minutes = (offset.inMinutes.abs() % 60).toString().padLeft(2, '0');
    final time =
        '${now.hour.toString().padLeft(2, '0')}:'
        '${now.minute.toString().padLeft(2, '0')}:'
        '${now.second.toString().padLeft(2, '0')}.'
        '${now.millisecond.toString().padLeft(3, '0')}';
    return '$time $sign$hours$minutes ';
  }

  static void log(String category, String message) {
    if (!enabled) return;
    debugPrint('${_timestamp()}[$category] $message');
  }

  /// UI state changes
  static void ui(String message) {
    if (enabled && uiEnabled) log('UI', message);
  }

  /// AG-UI event processing
  static void agui(String message) {
    if (enabled && agUiEvents) log('AG-UI', message);
  }

  /// Chat message flow
  static void chat(String message) {
    if (enabled && chatMessages) log('CHAT', message);
  }

  /// Message ID mapping - critical for debugging second response issue
  static void mapping(String message) {
    if (enabled && messageMapping) log('MAP', message);
  }

  /// Tool execution
  static void tool(String message) {
    if (enabled && toolsEnabled) log('TOOL', message);
  }

  /// Thread/SSE stream
  static void thread(String message) {
    if (enabled && threadEnabled) log('THREAD', message);
  }

  /// Services
  static void service(String message) {
    if (enabled && servicesEnabled) log('SVC', message);
  }

  /// Canvas
  static void canvasLog(String message) {
    if (enabled && canvasEnabled) log('CANVAS', message);
  }

  /// Network/connection management
  static void network(String message) {
    if (enabled && networkEnabled) log('NET', message);
  }

  /// Authentication flow
  static void auth(String message) {
    if (enabled && authEnabled) log('AUTH', message);
  }

  /// Warning - always shown when enabled
  static void warn(String message) {
    if (enabled) log('WARN', '⚠️ $message');
  }

  /// Error - always shown when enabled
  static void error(String message) {
    if (enabled) log('ERROR', '❌ $message');
  }
}
