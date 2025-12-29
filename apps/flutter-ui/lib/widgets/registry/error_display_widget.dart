import 'package:flutter/material.dart';

import 'package:soliplex/widgets/registry/widget_utils.dart';

/// ErrorDisplay widget for showing error messages.
class ErrorDisplayWidget extends StatelessWidget {
  const ErrorDisplayWidget({required this.message, super.key, this.color});

  /// Create from JSON data.
  ///
  /// Expected data format:
  /// ```json
  /// {
  ///   "message": "An error occurred",
  ///   "color": 4294198070  // Optional error color
  /// }
  /// ```
  factory ErrorDisplayWidget.fromData(
    Map<String, dynamic> data,
  ) {
    return ErrorDisplayWidget(
      message: data['message'] as String? ?? 'An error occurred',
      color: parseColor(data['color']),
    );
  }
  final String message;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final errorColor = color ?? Colors.red.shade700;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.red.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.red.shade200),
      ),
      child: Row(
        children: [
          Icon(Icons.error_outline, color: errorColor),
          const SizedBox(width: 12),
          Expanded(
            child: Text(message, style: TextStyle(color: errorColor)),
          ),
        ],
      ),
    );
  }
}
