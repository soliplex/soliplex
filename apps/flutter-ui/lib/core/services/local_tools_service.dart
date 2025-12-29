import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';

/// Result of a local tool execution.
class LocalToolResult {
  LocalToolResult({
    required this.toolCallId,
    required this.toolName,
    required this.success,
    required this.result,
    this.error,
  });
  final String toolCallId;
  final String toolName;
  final bool success;
  final Map<String, dynamic> result;
  final String? error;

  Map<String, dynamic> toJson() => {
    'tool_call_id': toolCallId,
    'tool_name': toolName,
    'success': success,
    'result': result,
    if (error != null) 'error': error,
  };

  @override
  String toString() =>
      'LocalToolResult($toolName: ${success ? "success" : "error: $error"})';
}

/// Definition of a local tool.
class LocalToolDefinition {
  const LocalToolDefinition({
    required this.name,
    required this.description,
    required this.parameters,
    required this.execute,
  });
  final String name;
  final String description;
  final Map<String, dynamic> parameters;
  final Future<Map<String, dynamic>> Function(Map<String, dynamic> args)
  execute;

  /// Convert to AG-UI tool format for sending to server.
  Map<String, dynamic> toAgUiTool() => {
    'name': name,
    'description': description,
    'parameters': parameters,
  };
}

/// Service for managing and executing local (client-side) tools.
///
/// Local tools are executed on the client instead of the server,
/// enabling access to device capabilities like GPS, camera, etc.
class LocalToolsService {
  LocalToolsService._();

  static final LocalToolsService _instance = LocalToolsService._();
  static LocalToolsService get instance => _instance;

  /// Registry of available local tools.
  final Map<String, LocalToolDefinition> _tools = {};

  /// Stream controller for tool execution results.
  final _resultController = StreamController<LocalToolResult>.broadcast();

  /// Stream of tool execution results.
  Stream<LocalToolResult> get results => _resultController.stream;

  /// Lock to prevent concurrent location permission requests.
  /// Uses Completer pattern - if a request is in-flight (not completed), others
  /// wait.
  Completer<LocationPermission>? _permissionCompleter;

  /// Initialize with default tools.
  void initialize() {
    // Register the get_my_location tool
    registerTool(_createGetMyLocationTool());

    // Register the genui_render tool (for dynamic widget rendering in chat)
    registerTool(_createGenUiRenderTool());

    // Register the canvas_render tool (for rendering widgets on canvas)
    registerTool(_createCanvasRenderTool());

    debugPrint('LocalToolsService: Initialized with ${_tools.length} tools');
  }

  /// Register a local tool.
  void registerTool(LocalToolDefinition tool) {
    _tools[tool.name] = tool;
    debugPrint('LocalToolsService: Registered tool "${tool.name}"');
  }

  /// Check if a tool is registered locally.
  bool hasLocalTool(String toolName) => _tools.containsKey(toolName);

  /// Get all registered tool definitions.
  List<LocalToolDefinition> get tools => _tools.values.toList();

  /// Get tool definitions in AG-UI format.
  List<Map<String, dynamic>> getAgUiToolDefinitions() {
    return _tools.values.map((t) => t.toAgUiTool()).toList();
  }

  /// Execute a local tool.
  ///
  /// Returns a LocalToolResult with the execution result.
  Future<LocalToolResult> executeTool(
    String toolCallId,
    String toolName,
    Map<String, dynamic> arguments,
  ) async {
    final tool = _tools[toolName];
    if (tool == null) {
      final result = LocalToolResult(
        toolCallId: toolCallId,
        toolName: toolName,
        success: false,
        result: {},
        error: 'Unknown local tool: $toolName',
      );
      _resultController.add(result);
      return result;
    }

    debugPrint(
      'LocalToolsService: Executing tool "$toolName" with args: $arguments',
    );

    try {
      final resultData = await tool.execute(arguments);
      final result = LocalToolResult(
        toolCallId: toolCallId,
        toolName: toolName,
        success: true,
        result: resultData,
      );
      _resultController.add(result);
      debugPrint('LocalToolsService: Tool "$toolName" completed successfully');
      return result;
    } on Object catch (e, stackTrace) {
      debugPrint('LocalToolsService: Tool "$toolName" failed: $e\n$stackTrace');
      final result = LocalToolResult(
        toolCallId: toolCallId,
        toolName: toolName,
        success: false,
        result: {},
        error: e.toString(),
      );
      _resultController.add(result);
      return result;
    }
  }

  /// Create the get_my_location tool definition.
  LocalToolDefinition _createGetMyLocationTool() {
    return LocalToolDefinition(
      name: 'get_location',
      description: "Get the user's current location (lat, long)",
      parameters: {'type': 'object', 'properties': {}},
      execute: (args) async {
        return _executeGetMyLocation(args);
      },
    );
  }

  /// Execute the get_my_location tool.
  Future<Map<String, dynamic>> _executeGetMyLocation(
    Map<String, dynamic> args,
  ) async {
    final highAccuracy = args['high_accuracy'] as bool? ?? false;

    // Check if location services are enabled
    final serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      throw Exception(
        'Location services are disabled. Please enable location services.',
      );
    }

    // Check/request permission with lock to prevent concurrent requests
    debugPrint('LocalToolsService: Checking location permission...');
    var permission = await Geolocator.checkPermission();
    debugPrint('LocalToolsService: Current permission: $permission');
    var justGrantedPermission = false;
    if (permission == LocationPermission.denied) {
      // Use Completer lock to prevent concurrent permission requests.
      // Check if an uncompleted request is in-flight - if so, wait for it.
      final existingCompleter = _permissionCompleter;
      if (existingCompleter != null && !existingCompleter.isCompleted) {
        debugPrint(
          // ignore: lines_longer_than_80_chars (auto-documented)
          'LocalToolsService: Permission request already in progress, waiting...',
        );
        permission = await existingCompleter.future;
      } else {
        // Create new Completer SYNCHRONOUSLY before any await - makes this
        // atomic
        final completer = Completer<LocationPermission>();
        _permissionCompleter = completer;

        try {
          debugPrint('LocalToolsService: Requesting location permission...');
          permission = await Geolocator.requestPermission();
          debugPrint(
            'LocalToolsService: After request, permission: $permission',
          );
          completer.complete(permission);
        } on Object catch (e) {
          completer.completeError(e);
          rethrow;
        }
      }

      if (permission == LocationPermission.denied) {
        throw Exception(
          'Location permission denied. Please grant location access.',
        );
      }
      // Permission was just granted - macOS needs time to propagate
      justGrantedPermission = true;
      debugPrint(
        // ignore: lines_longer_than_80_chars (auto-documented)
        'LocalToolsService: Permission granted, waiting for system to propagate...',
      );
    }

    if (permission == LocationPermission.deniedForever) {
      throw Exception(
        'Location permissions are permanently denied. '
        // ignore: lines_longer_than_80_chars (auto-documented)
        'Please enable in System Preferences > Security & Privacy > Privacy > Location Services.',
      );
    }

    // Get current position with retry for freshly granted permissions
    debugPrint(
      // ignore: lines_longer_than_80_chars (auto-documented)
      'LocalToolsService: Getting current position (highAccuracy=$highAccuracy)...',
    );

    Position? position;
    final retryCount = justGrantedPermission ? 3 : 2;
    Exception? lastError;

    for (var attempt = 1; attempt <= retryCount; attempt++) {
      try {
        // Small delay after permission grant to let macOS propagate
        if (justGrantedPermission && attempt == 1) {
          await Future<void>.delayed(const Duration(milliseconds: 500));
        }

        debugPrint(
          'LocalToolsService: Attempt $attempt - calling getCurrentPosition...',
        );
        position = await Geolocator.getCurrentPosition(
          locationSettings: LocationSettings(
            accuracy: highAccuracy
                ? LocationAccuracy.best
                : LocationAccuracy.medium,
            timeLimit: const Duration(seconds: 30),
          ),
        );
        break; // Success!
      } on Object catch (e) {
        lastError = e is Exception ? e : Exception(e.toString());
        debugPrint('LocalToolsService: Attempt $attempt failed: $e');

        if (attempt < retryCount) {
          // Wait before retry - permission may still be propagating
          debugPrint('LocalToolsService: Retrying in 1 second...');
          await Future<void>.delayed(const Duration(seconds: 1));
        }
      }
    }

    if (position == null) {
      throw lastError ?? Exception('Failed to get location');
    }

    debugPrint(
      // ignore: lines_longer_than_80_chars (auto-documented)
      'LocalToolsService: Got position: ${position.latitude}, ${position.longitude}',
    );

    return {
      'latitude': position.latitude,
      'longitude': position.longitude,
      'accuracy': position.accuracy,
      'altitude': position.altitude,
      'speed': position.speed,
      'speed_accuracy': position.speedAccuracy,
      'heading': position.heading,
      'heading_accuracy': position.headingAccuracy,
      'timestamp': position.timestamp.toIso8601String(),
      'is_mocked': position.isMocked,
    };
  }

  /// Create the genui_render tool definition.
  ///
  /// This tool allows the agent to render native UI widgets in the chat.
  /// Unlike other local tools, this one does NOT send a result back to the
  /// server.
  /// The widget is rendered directly in the chat UI.
  LocalToolDefinition _createGenUiRenderTool() {
    return LocalToolDefinition(
      name: 'genui_render',
      description: '''
Render a UI widget in the chat. Use this to display data cards, metrics, progress indicators, and other visual elements inline in the conversation. // ignore: lines_longer_than_80_chars (auto-documented)

Available widget_name options:
- "InfoCard": Display info with title, subtitle, icon, color
// ignore: lines_longer_than_80_chars (auto-documented)
- "MetricDisplay": Show a metric with label, value, unit, trend (up/down/neutral) // ignore: lines_longer_than_80_chars
- "DataList": Display a list of key-value pairs
- "ErrorDisplay": Show an error message
- "LoadingIndicator": Show a loading spinner with optional message
- "ActionButton": A clickable button
- "ProgressCard": Show a progress bar with label and percentage
// ignore: lines_longer_than_80_chars (auto-documented)
- "LocationCard": Display GPS coordinates with latitude, longitude, accuracy, city, country // ignore: lines_longer_than_80_chars
// ignore: lines_longer_than_80_chars (auto-documented)
- "GISCard": Display an OpenStreetMap with location marker and accuracy circle (tap to open interactive map) // ignore: lines_longer_than_80_chars

The data parameter contains the widget-specific properties as JSON.

Example for InfoCard:
{
  "widget_name": "InfoCard",
  "data": {
    "title": "Welcome",
    "subtitle": "Hello world",
    "icon": 58751
  }
}

Example for LocationCard:
{
  "widget_name": "LocationCard",
  "data": {
    "latitude": 37.7749,
    "longitude": -122.4194,
    "accuracy": 10.0,
    "city": "San Francisco",
    "country": "USA"
  }
}

Example for GISCard (single location):
{
  "widget_name": "GISCard",
  "data": {
    "latitude": 37.7749,
    "longitude": -122.4194,
    "accuracy": 10.0,
    "zoom": 15,
    "title": "Your Location",
    "showAccuracyCircle": true
  }
}

Example for GISCard with MULTIPLE locations (use "coordinates" array):
{
  "widget_name": "GISCard",
  "data": {
    "coordinates": [
      // ignore: lines_longer_than_80_chars (auto-documented)
      {"latitude": 37.7749, "longitude": -122.4194, "label": "San Francisco", "color": "#FF0000"}, // ignore: lines_longer_than_80_chars
      // ignore: lines_longer_than_80_chars (auto-documented)
      {"latitude": 34.0522, "longitude": -118.2437, "label": "Los Angeles", "color": "#00FF00"}, // ignore: lines_longer_than_80_chars
      // ignore: lines_longer_than_80_chars (auto-documented)
      {"latitude": 47.6062, "longitude": -122.3321, "label": "Seattle", "color": "#0000FF"} // ignore: lines_longer_than_80_chars
    ],
    "title": "West Coast Cities",
    "showAccuracyCircle": false
  }
}
// ignore: lines_longer_than_80_chars (auto-documented)
Note: When using "coordinates" array, the map automatically zooms to fit all points.''',
      parameters: {
        'type': 'object',
        'properties': {
          'widget_name': {
            'type': 'string',
            'description':
                // ignore: lines_longer_than_80_chars (auto-documented)
                'Name of the widget to render: InfoCard, MetricDisplay, DataList, ErrorDisplay, LoadingIndicator, ActionButton, ProgressCard, LocationCard, GISCard',
          },
          'data': {
            'type': 'object',
            'description': 'Widget-specific data as JSON object',
            'default': {},
          },
        },
        'required': ['widget_name'],
      },
      // This execute function is never actually called - genui_render is
      // handled specially in chat_content.dart to render widgets directly
      execute: (args) async => {'rendered': true},
    );
  }

  /// Create the canvas_render tool definition.
  ///
  /// This tool allows the agent to render widgets on the canvas area (in Canvas
  /// layout mode).
  /// Unlike other local tools, this one does NOT send a result back to the
  /// server.
  LocalToolDefinition _createCanvasRenderTool() {
    return LocalToolDefinition(
      name: 'canvas_render',
      description: '''
Render a UI widget on the canvas area. The canvas is a separate display area (visible in Canvas layout mode) where you can build up dashboards and visualizations. // ignore: lines_longer_than_80_chars

Available widget_name options (same as genui_render):
- "InfoCard": Display info with title, subtitle, icon, color
// ignore: lines_longer_than_80_chars (auto-documented)
- "MetricDisplay": Show a metric with label, value, unit, trend (up/down/neutral) // ignore: lines_longer_than_80_chars
- "DataList": Display a list of key-value pairs
- "ErrorDisplay": Show an error message
- "LoadingIndicator": Show a loading spinner with optional message
- "ActionButton": A clickable button
- "ProgressCard": Show a progress bar with label and percentage
- "LocationCard": Display GPS coordinates
- "GISCard": Display an OpenStreetMap with location marker

The position parameter controls how the widget is added:
- "append" (default): Add widget to the end of the canvas
- "replace": Clear canvas and show only this widget
- "clear": Clear the canvas (widget_name and data are ignored)

Example - Add a metric to canvas:
{
  "widget_name": "MetricDisplay",
  "data": {
    "label": "Temperature",
    "value": "72",
    "unit": "°F",
    "trend": "up"
  },
  "position": "append"
}

Example - Replace canvas with a single card:
{
  "widget_name": "InfoCard",
  "data": {"title": "Dashboard", "subtitle": "Updated just now"},
  "position": "replace"
}

Example - Clear the canvas:
{
  "widget_name": "",
  "data": {},
  "position": "clear"
}''',
      parameters: {
        'type': 'object',
        'properties': {
          'widget_name': {
            'type': 'string',
            'description':
                // ignore: lines_longer_than_80_chars (auto-documented)
                'Name of the widget to render: InfoCard, MetricDisplay, DataList, ErrorDisplay, LoadingIndicator, ActionButton, ProgressCard, LocationCard, GISCard',
          },
          'data': {
            'type': 'object',
            'description': 'Widget-specific data as JSON object',
            'default': {},
          },
          'position': {
            'type': 'string',
            'enum': ['append', 'replace', 'clear'],
            'description':
                // ignore: lines_longer_than_80_chars (auto-documented)
                'How to add the widget: append (add to end), replace (clear and show only this), clear (remove all)',
            'default': 'append',
          },
        },
        'required': ['widget_name'],
      },
      // This execute function is never actually called - canvas_render is
      // handled specially in chat_content.dart to render on canvas
      execute: (args) async => {'rendered': true},
    );
  }

  void dispose() {
    _resultController.close();
  }
}

/// Riverpod provider for LocalToolsService.
final localToolsServiceProvider = Provider<LocalToolsService>((ref) {
  final service = LocalToolsService.instance;
  service.initialize();
  return service;
});
