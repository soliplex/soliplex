import 'package:flutter/material.dart';
import 'package:soliplex_frontend/features/inspector/models/http_event_group.dart';
import 'package:soliplex_frontend/shared/utils/format_utils.dart';

/// Extension on [ColorScheme] to provide warning color.
///
/// Material Design 3 ColorScheme doesn't include a warning color.
/// This extension derives one that adapts to light/dark themes.
extension WarningColors on ColorScheme {
  /// Warning color that adapts to the current theme brightness.
  Color get warning =>
      brightness == Brightness.light ? Colors.orange : Colors.orange.shade300;
}

/// Builds status display widget based on event group status.
class HttpStatusDisplay extends StatelessWidget {
  const HttpStatusDisplay({
    required this.group,
    super.key,
  });

  static const double _spinnerSize = 12;
  static const double _spinnerStroke = 2;

  final HttpEventGroup group;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = _colorForStatus(group.status, theme.colorScheme);
    final statusText = _buildStatusText();

    final child = group.hasSpinner
        ? _buildSpinnerStatus(statusText, color, theme)
        : _buildTextStatus(statusText, color, theme);

    return Semantics(
      label: group.statusDescription,
      child: ExcludeSemantics(child: child),
    );
  }

  /// Maps HTTP event status to theme color.
  Color _colorForStatus(HttpEventStatus status, ColorScheme colorScheme) {
    return switch (status) {
      HttpEventStatus.pending => colorScheme.onSurfaceVariant,
      HttpEventStatus.success => colorScheme.tertiary,
      HttpEventStatus.clientError => colorScheme.warning,
      HttpEventStatus.serverError => colorScheme.error,
      HttpEventStatus.networkError => colorScheme.error,
      HttpEventStatus.streaming => colorScheme.secondary,
      HttpEventStatus.streamComplete => colorScheme.tertiary,
      HttpEventStatus.streamError => colorScheme.error,
    };
  }

  /// Builds formatted status text from event group data.
  String _buildStatusText() {
    return switch (group.status) {
      HttpEventStatus.pending => 'pending...',
      HttpEventStatus.success => '${group.response!.statusCode} OK '
          '(${group.response!.duration.toHttpDurationString()}, '
          '${group.response!.bodySize.toHttpBytesString()})',
      HttpEventStatus.clientError => '${group.response!.statusCode} '
          '(${group.response!.duration.toHttpDurationString()})',
      HttpEventStatus.serverError => '${group.response!.statusCode} '
          '(${group.response!.duration.toHttpDurationString()})',
      HttpEventStatus.networkError => '${group.error!.exception.runtimeType} '
          '(${group.error!.duration.toHttpDurationString()})',
      HttpEventStatus.streaming => group.streamEnd != null
          ? 'streaming... '
              '(${group.streamEnd!.bytesReceived.toHttpBytesString()})'
          : 'streaming...',
      HttpEventStatus.streamComplete =>
        'complete (${group.streamEnd!.duration.toHttpDurationString()}, '
            '${group.streamEnd!.bytesReceived.toHttpBytesString()})',
      HttpEventStatus.streamError =>
        'error (${group.streamEnd!.duration.toHttpDurationString()})',
    };
  }

  Widget _buildTextStatus(String text, Color color, ThemeData theme) {
    return Text(
      text,
      style: theme.textTheme.bodySmall?.copyWith(color: color),
    );
  }

  Widget _buildSpinnerStatus(String text, Color color, ThemeData theme) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          width: _spinnerSize,
          height: _spinnerSize,
          child: CircularProgressIndicator(
            strokeWidth: _spinnerStroke,
            color: color,
          ),
        ),
        const SizedBox(width: 8),
        Text(
          text,
          style: theme.textTheme.bodySmall?.copyWith(
            fontStyle: FontStyle.italic,
            color: color,
          ),
        ),
      ],
    );
  }
}
