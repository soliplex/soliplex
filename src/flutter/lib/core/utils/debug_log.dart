/// Centralized debug logging utility.
///
/// Set enabled to false to disable all debug logging.
/// Set individual flags to enable specific categories.
library;

import 'package:flutter/foundation.dart';

class DebugLog {
  /// Master switch - set to false to disable all logging
  static bool enabled = true;

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

  static void log(String category, String message) {
    if (!enabled) return;
    debugPrint('[$category] $message');
  }

  /// UI state changes
  static void ui(String message) {
    if (enabled && uiEnabled) {
      debugPrint('[UI] $message');
    }
  }

  /// AG-UI event processing
  static void agui(String message) {
    if (enabled && agUiEvents) {
      debugPrint('[AG-UI] $message');
    }
  }

  /// Chat message flow
  static void chat(String message) {
    if (enabled && chatMessages) {
      debugPrint('[CHAT] $message');
    }
  }

  /// Message ID mapping - critical for debugging second response issue
  static void mapping(String message) {
    if (enabled && messageMapping) {
      debugPrint('[MAP] $message');
    }
  }

  /// Tool execution
  static void tool(String message) {
    if (enabled && toolsEnabled) {
      debugPrint('[TOOL] $message');
    }
  }

  /// Thread/SSE stream
  static void thread(String message) {
    if (enabled && threadEnabled) {
      debugPrint('[THREAD] $message');
    }
  }

  /// Services
  static void service(String message) {
    if (enabled && servicesEnabled) {
      debugPrint('[SVC] $message');
    }
  }

  /// Canvas
  static void canvasLog(String message) {
    if (enabled && canvasEnabled) {
      debugPrint('[CANVAS] $message');
    }
  }

  /// Network/connection management
  static void network(String message) {
    if (enabled && networkEnabled) {
      debugPrint('[NET] $message');
    }
  }

  /// Authentication flow
  static void auth(String message) {
    if (enabled && authEnabled) {
      debugPrint('[AUTH] $message');
    }
  }

  /// Warning - always shown when enabled
  static void warn(String message) {
    if (enabled) {
      debugPrint('[WARN] ⚠️ $message');
    }
  }

  /// Error - always shown when enabled
  static void error(String message) {
    if (enabled) {
      debugPrint('[ERROR] ❌ $message');
    }
  }
}
