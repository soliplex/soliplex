import 'package:flutter/material.dart';

import 'package:soliplex/widgets/registry/widget_utils.dart';

/// ProgressCard widget for displaying progress bars with labels.
class ProgressCardWidget extends StatelessWidget {
  const ProgressCardWidget({
    required this.label,
    required this.progress,
    super.key,
    this.color,
  });

  /// Create from JSON data.
  ///
  /// Expected data format:
  /// ```json
  /// {
  ///   "label": "Upload Progress",
  ///   "progress": 0.75,  // 0.0 to 1.0
  ///   "color": 4280391411  // Optional progress color
  /// }
  /// ```
  factory ProgressCardWidget.fromData(
    Map<String, dynamic> data,
  ) {
    return ProgressCardWidget(
      label: data['label'] as String? ?? '',
      progress: parseDouble(data['progress']) ?? 0.0,
      color: parseColor(data['color']),
    );
  }
  final String label;
  final double progress;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [Text(label), Text('${(progress * 100).toInt()}%')],
            ),
            const SizedBox(height: 8),
            LinearProgressIndicator(
              value: progress.clamp(0.0, 1.0),
              backgroundColor: Colors.grey.shade200,
              valueColor: AlwaysStoppedAnimation(color ?? Colors.blue),
            ),
          ],
        ),
      ),
    );
  }
}
