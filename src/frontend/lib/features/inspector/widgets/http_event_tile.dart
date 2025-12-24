import 'package:flutter/material.dart';
import 'package:soliplex_frontend/features/inspector/models/http_event_group.dart';
import 'package:soliplex_frontend/features/inspector/widgets/http_status_display.dart';
import 'package:soliplex_frontend/shared/utils/format_utils.dart';

/// Displays a grouped HTTP request with its outcome.
///
/// Groups related events (request + response/error) into a single tile
/// showing method, path, timestamp, and result status.
class HttpEventTile extends StatelessWidget {
  const HttpEventTile({
    required this.group,
    super.key,
  });

  /// The grouped events for a single HTTP request.
  final HttpEventGroup group;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Semantics(
      label: group.semanticLabel,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildRequestLine(theme),
            const SizedBox(height: 4),
            _buildResultLine(theme),
          ],
        ),
      ),
    );
  }

  Widget _buildRequestLine(ThemeData theme) {
    final colorScheme = theme.colorScheme;

    return Row(
      children: [
        Text(
          group.methodLabel,
          style: theme.textTheme.bodyMedium?.copyWith(
            fontWeight: FontWeight.bold,
            color: group.isStream ? colorScheme.secondary : colorScheme.primary,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            group.pathWithQuery,
            style: theme.textTheme.bodyMedium,
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }

  Widget _buildResultLine(ThemeData theme) {
    final colorScheme = theme.colorScheme;
    final timestamp = group.timestamp.toHttpTimeString();

    return Row(
      children: [
        Text(
          timestamp,
          style: theme.textTheme.bodySmall?.copyWith(
            color: colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(width: 4),
        Text(
          '→',
          style: theme.textTheme.bodySmall?.copyWith(
            color: colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(width: 4),
        Expanded(child: HttpStatusDisplay(group: group)),
      ],
    );
  }
}
