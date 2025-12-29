import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'package:soliplex/widgets/registry/widget_utils.dart';

/// InfoCard widget for displaying information with title, subtitle, and
/// optional icon.
class InfoCardWidget extends StatelessWidget {
  const InfoCardWidget({
    required this.title,
    super.key,
    this.subtitle,
    this.icon,
    this.color,
    this.onTap,
  });

  /// Create from JSON data.
  ///
  /// Expected data format:
  /// ```json
  /// {
  ///   "title": "Card Title",
  ///   "subtitle": "Optional subtitle",
  ///   "icon": 58751,  // IconData codePoint
  ///   "color": 4280391411  // Color value in ARGB32
  /// }
  /// ```
  factory InfoCardWidget.fromData(
    Map<String, dynamic> data,
    void Function(String, Map<String, dynamic>)? onEvent,
  ) {
    return InfoCardWidget(
      title: data['title'] as String? ?? '',
      subtitle: data['subtitle'] as String?,
      icon: parseIcon(data['icon']),
      color: parseColor(data['color']),
      onTap: onEvent != null ? () => onEvent('tap', {}) : null,
    );
  }
  final String title;
  final String? subtitle;
  final IconData? icon;
  final Color? color;
  final VoidCallback? onTap;

  String _copyableText() {
    final buffer = StringBuffer();
    buffer.writeln(title);
    if (subtitle != null) {
      buffer.writeln(subtitle);
    }
    return buffer.toString();
  }

  void _copyToClipboard() {
    Clipboard.setData(ClipboardData(text: _copyableText()));
  }

  @override
  Widget build(BuildContext context) {
    final baseColor = color ?? Theme.of(context).colorScheme.primary;

    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: baseColor.withAlpha(25),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(icon, color: baseColor),
                ),
                const SizedBox(width: 16),
              ],
              Flexible(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    SelectableText(
                      title,
                      style: Theme.of(context).textTheme.titleMedium,
                      maxLines: 2,
                    ),
                    if (subtitle != null)
                      SelectableText(
                        subtitle!,
                        style: Theme.of(context).textTheme.bodySmall,
                        maxLines: 3,
                      ),
                  ],
                ),
              ),
              IconButton(
                icon: const Icon(Icons.copy, size: 18),
                onPressed: _copyToClipboard,
                tooltip: 'Copy to clipboard',
                visualDensity: VisualDensity.compact,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
