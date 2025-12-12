import 'package:flutter/material.dart';

import 'widget_utils.dart';

/// MetricDisplay widget for showing a metric value with label, unit, and trend.
class MetricDisplayWidget extends StatelessWidget {
  final String label;
  final String value;
  final String? unit;
  final String? trend; // 'up', 'down', 'neutral'
  final Color? color;

  const MetricDisplayWidget({
    super.key,
    required this.label,
    required this.value,
    this.unit,
    this.trend,
    this.color,
  });

  /// Create from JSON data.
  ///
  /// Expected data format:
  /// ```json
  /// {
  ///   "label": "Revenue",
  ///   "value": "1,234",
  ///   "unit": "USD",
  ///   "trend": "up",  // "up", "down", or "neutral"
  ///   "color": 4280391411
  /// }
  /// ```
  factory MetricDisplayWidget.fromData(
    Map<String, dynamic> data,
    void Function(String, Map<String, dynamic>)? onEvent,
  ) {
    return MetricDisplayWidget(
      label: data['label'] as String? ?? '',
      value: data['value']?.toString() ?? '',
      unit: data['unit'] as String?,
      trend: data['trend'] as String?,
      color: parseColor(data['color']),
    );
  }

  @override
  Widget build(BuildContext context) {
    Color trendColor = Colors.grey;
    IconData trendIcon = Icons.remove;

    if (trend == 'up') {
      trendColor = Colors.green;
      trendIcon = Icons.trending_up;
    } else if (trend == 'down') {
      trendColor = Colors.red;
      trendIcon = Icons.trending_down;
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              label,
              style: Theme.of(
                context,
              ).textTheme.bodySmall?.copyWith(color: Colors.grey.shade600),
            ),
            const SizedBox(height: 8),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  value,
                  style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                    color: color,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                if (unit != null) ...[
                  const SizedBox(width: 4),
                  Text(
                    unit!,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Colors.grey.shade600,
                    ),
                  ),
                ],
                const Spacer(),
                if (trend != null) Icon(trendIcon, color: trendColor, size: 24),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
