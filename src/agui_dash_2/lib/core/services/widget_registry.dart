import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../widgets/registry/info_card_widget.dart';
import '../../widgets/registry/metric_display_widget.dart';
import '../../widgets/registry/data_list_widget.dart';
import '../../widgets/registry/error_display_widget.dart';
import '../../widgets/registry/loading_indicator_widget.dart';
import '../../widgets/registry/action_button_widget.dart';
import '../../widgets/registry/progress_card_widget.dart';
import '../../widgets/registry/location_card_widget.dart';
import '../../widgets/registry/gis_card_widget.dart';
import '../../widgets/registry/search_widget.dart';
import '../../widgets/registry/skills_card_widget.dart';
import '../../widgets/registry/project_card_widget.dart';
import '../../widgets/registry/note_card_widget.dart';
import '../../widgets/registry/code_card_widget.dart';
import '../../widgets/registry/markdown_card_widget.dart';

/// Widget builder function signature.
///
/// Takes context, data map, and optional event callback.
/// Returns a Widget to render.
typedef WidgetBuilder =
    Widget Function(
      BuildContext context,
      Map<String, dynamic> data,
      void Function(String eventName, Map<String, dynamic> args)? onEvent,
    );

/// Registry for native GenUI widgets.
///
/// Maps widget names to builder functions. Agents send widget_name + JSON data,
/// and the registry renders the appropriate native Flutter widget.
class WidgetRegistry {
  final Map<String, WidgetBuilder> _builders = {};

  /// Creates a new widget registry with all default widgets registered.
  WidgetRegistry() {
    _registerDefaultWidgets();
  }

  /// Register default widgets internally during construction.
  void _registerDefaultWidgets() {
    register('InfoCard', (context, data, onEvent) {
      return InfoCardWidget.fromData(data, onEvent);
    });

    register('MetricDisplay', (context, data, onEvent) {
      return MetricDisplayWidget.fromData(data, onEvent);
    });

    register('DataList', (context, data, onEvent) {
      return DataListWidget.fromData(data, onEvent);
    });

    register('ErrorDisplay', (context, data, onEvent) {
      return ErrorDisplayWidget.fromData(data, onEvent);
    });

    register('LoadingIndicator', (context, data, onEvent) {
      return LoadingIndicatorWidget.fromData(data, onEvent);
    });

    register('ActionButton', (context, data, onEvent) {
      return ActionButtonWidget.fromData(data, onEvent);
    });

    register('ProgressCard', (context, data, onEvent) {
      return ProgressCardWidget.fromData(data, onEvent);
    });

    register('LocationCard', (context, data, onEvent) {
      return LocationCardWidget.fromData(data, onEvent);
    });

    register('GISCard', (context, data, onEvent) {
      return GISCardWidget.fromData(data, onEvent);
    });

    register('SearchWidget', (context, data, onEvent) {
      return SearchWidget(data: data, onEvent: onEvent);
    });

    register('SkillsCard', (context, data, onEvent) {
      return SkillsCardWidget.fromData(data, onEvent);
    });

    register('ProjectCard', (context, data, onEvent) {
      return ProjectCardWidget.fromData(data, onEvent);
    });

    // Canvas content widgets (for send-to-canvas feature)
    register('NoteCard', (context, data, onEvent) {
      return NoteCardWidget.fromData(data, onEvent);
    });

    register('CodeCard', (context, data, onEvent) {
      return CodeCardWidget.fromData(data, onEvent);
    });

    register('MarkdownCard', (context, data, onEvent) {
      return MarkdownCardWidget.fromData(data, onEvent);
    });

    // Alias 'display' to MarkdownCard for generic content display
    register('display', (context, data, onEvent) {
      return MarkdownCardWidget.fromData(data, onEvent);
    });
  }

  /// Register a widget builder for a given name.
  void register(String widgetName, WidgetBuilder builder) {
    _builders[widgetName.toLowerCase()] = builder;
  }

  /// Check if a widget is registered.
  bool hasWidget(String widgetName) {
    return _builders.containsKey(widgetName.toLowerCase());
  }

  /// Build a widget by name with the given data.
  ///
  /// Returns null if widget is not registered.
  Widget? build(
    BuildContext context,
    String widgetName,
    Map<String, dynamic> data, {
    void Function(String eventName, Map<String, dynamic> args)? onEvent,
  }) {
    final builder = _builders[widgetName.toLowerCase()];
    if (builder == null) return null;
    return builder(context, data, onEvent);
  }

  /// Get list of all registered widget names.
  List<String> get registeredWidgets => _builders.keys.toList();
}

/// Riverpod provider for the widget registry.
///
/// Creates a single instance per provider scope. Default widgets are
/// registered during construction. Tests can override with custom instances.
final widgetRegistryProvider = Provider<WidgetRegistry>((ref) {
  return WidgetRegistry();
});
