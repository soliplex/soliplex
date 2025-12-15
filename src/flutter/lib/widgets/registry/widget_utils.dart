import 'package:flutter/material.dart';

/// Utility functions for safe data parsing in widget factories.

/// Parse a value that might be int or String to a Color.
///
/// Supports:
/// - int: Direct color value (e.g., 4280391411)
/// - String: Numeric string (e.g., "4280391411")
/// - String: Hex with 0x prefix (e.g., "0xFF4CAF50")
/// - String: Hex with # prefix (e.g., "#FF0000" or "#80FF0000")
Color? parseColor(dynamic value) {
  if (value == null) return null;
  if (value is int) return Color(value);
  if (value is String) {
    final str = value.trim();

    // Try parsing as hex (0xFF...)
    if (str.startsWith('0x') || str.startsWith('0X')) {
      final intVal = int.tryParse(str);
      if (intVal != null) return Color(intVal);
    }

    // Try parsing as hex with # prefix (#RRGGBB or #AARRGGBB)
    if (str.startsWith('#')) {
      final hex = str.substring(1);
      if (hex.length == 6) {
        // #RRGGBB -> add full alpha
        final intVal = int.tryParse('FF$hex', radix: 16);
        if (intVal != null) return Color(intVal);
      } else if (hex.length == 8) {
        // #AARRGGBB
        final intVal = int.tryParse(hex, radix: 16);
        if (intVal != null) return Color(intVal);
      }
    }

    // Try as decimal
    final intVal = int.tryParse(str);
    if (intVal != null) return Color(intVal);
  }
  return null;
}

/// Parse a value that might be num or String to double.
double? parseDouble(dynamic value) {
  if (value == null) return null;
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value);
  return null;
}

/// Parse a value that might be num or String to int.
int? parseInt(dynamic value) {
  if (value == null) return null;
  if (value is int) return value;
  if (value is num) return value.toInt();
  if (value is String) return int.tryParse(value);
  return null;
}

/// Parse an IconData from code point value.
IconData? parseIcon(dynamic value) {
  final codePoint = parseInt(value);
  if (codePoint == null) return null;
  return IconData(codePoint, fontFamily: 'MaterialIcons');
}
