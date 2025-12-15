import 'package:flutter/material.dart';
import 'package:soliplex/core/models/error_types.dart';

/// A friendly, expandable error card that replaces harsh red error boxes.
///
/// Displays a brief friendly message by default with an option to expand
/// and see technical details. Styling is muted and non-alarming.
class FriendlyErrorCard extends StatefulWidget {
  const FriendlyErrorCard({
    required this.errorInfo,
    super.key,
    this.fallbackMessage,
    this.onRetry,
  });

  /// Create from legacy error message string (for backwards compatibility)
  factory FriendlyErrorCard.fromMessage(
    String message, {
    VoidCallback? onRetry,
  }) {
    // Try to classify the error based on message content
    ChatErrorInfo errorInfo;
    if (message.toLowerCase().contains('connection') ||
        message.toLowerCase().contains('network') ||
        message.toLowerCase().contains('timeout') ||
        message.toLowerCase().contains('socket')) {
      errorInfo = ChatErrorInfo.network(details: message);
    } else {
      errorInfo = ChatErrorInfo.server(message: message);
    }
    return FriendlyErrorCard(
      errorInfo: errorInfo,
      fallbackMessage: message,
      onRetry: onRetry,
    );
  }

  /// The error information to display
  final ChatErrorInfo errorInfo;

  /// Fallback error message if errorInfo is minimal
  final String? fallbackMessage;

  /// Callback when retry is tapped (only shown if errorInfo.canRetry is true)
  final VoidCallback? onRetry;

  @override
  State<FriendlyErrorCard> createState() => _FriendlyErrorCardState();
}

class _FriendlyErrorCardState extends State<FriendlyErrorCard> {
  bool _expanded = false;

  bool get _hasDetails =>
      widget.errorInfo.technicalDetails != null ||
      widget.errorInfo.errorCode != null;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Container(
        decoration: BoxDecoration(
          color: colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: colorScheme.outlineVariant),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Header row with icon, message, and actions
            _buildHeader(context, colorScheme),

            // Expandable details section
            if (_expanded && _hasDetails) _buildDetails(context, colorScheme),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context, ColorScheme colorScheme) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        children: [
          // Emoji icon
          Text(widget.errorInfo.icon, style: const TextStyle(fontSize: 18)),
          const SizedBox(width: 10),

          // Friendly message
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  widget.errorInfo.friendlyMessage,
                  style: TextStyle(
                    color: colorScheme.onSurfaceVariant,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                // Show brief error snippet for tool errors
                if (widget.errorInfo.type == ChatErrorType.tool &&
                    widget.errorInfo.technicalDetails != null)
                  Text(
                    _truncate(widget.errorInfo.technicalDetails!, 50),
                    style: TextStyle(
                      color: colorScheme.onSurfaceVariant.withValues(
                        alpha: 0.7,
                      ),
                      fontSize: 12,
                    ),
                  ),
              ],
            ),
          ),

          // Retry button (for network errors)
          if (widget.errorInfo.canRetry && widget.onRetry != null)
            TextButton(
              onPressed: widget.onRetry,
              style: TextButton.styleFrom(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 6,
                ),
                minimumSize: Size.zero,
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
              child: Text(
                'Retry',
                style: TextStyle(
                  color: colorScheme.primary,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),

          // Expand/collapse button (if has details)
          if (_hasDetails)
            IconButton(
              onPressed: () => setState(() => _expanded = !_expanded),
              icon: Icon(
                _expanded ? Icons.expand_less : Icons.expand_more,
                color: colorScheme.onSurfaceVariant,
                size: 20,
              ),
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
              tooltip: _expanded ? 'Hide details' : 'Show details',
            ),
        ],
      ),
    );
  }

  Widget _buildDetails(BuildContext context, ColorScheme colorScheme) {
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Error code if present
          if (widget.errorInfo.errorCode != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text(
                'Error: ${widget.errorInfo.errorCode}',
                style: TextStyle(
                  color: colorScheme.onSurfaceVariant,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  fontFamily: 'monospace',
                ),
              ),
            ),

          // Technical details
          if (widget.errorInfo.technicalDetails != null)
            SelectableText(
              widget.errorInfo.technicalDetails!,
              style: TextStyle(
                color: colorScheme.onSurfaceVariant.withValues(alpha: 0.8),
                fontSize: 12,
                fontFamily: 'monospace',
              ),
            ),
        ],
      ),
    );
  }

  String _truncate(String text, int maxLength) {
    if (text.length <= maxLength) return text;
    return '${text.substring(0, maxLength)}...';
  }
}
