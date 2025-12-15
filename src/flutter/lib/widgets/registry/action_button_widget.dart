import 'package:flutter/material.dart';

import 'package:soliplex/widgets/registry/widget_utils.dart';

/// ActionButton widget for interactive buttons.
class ActionButtonWidget extends StatelessWidget {
  const ActionButtonWidget({
    required this.label,
    super.key,
    this.color,
    this.onPressed,
  });

  /// Create from JSON data.
  ///
  /// Expected data format:
  /// ```json
  /// {
  ///   "label": "Click Me",
  ///   "color": 4280391411  // Optional button color
  /// }
  /// ```
  factory ActionButtonWidget.fromData(
    Map<String, dynamic> data,
    void Function(String, Map<String, dynamic>)? onEvent,
  ) {
    return ActionButtonWidget(
      label: data['label'] as String? ?? 'Action',
      color: parseColor(data['color']),
      onPressed: onEvent != null ? () => onEvent('pressed', data) : null,
    );
  }
  final String label;
  final Color? color;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      style: color != null
          ? ElevatedButton.styleFrom(backgroundColor: color)
          : null,
      onPressed: onPressed,
      child: Text(label),
    );
  }
}
