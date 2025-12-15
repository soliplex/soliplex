import 'package:flutter/material.dart';

/// Unified suggestion chip component.
///
/// Consolidates the various suggestion chip implementations into a single,
/// configurable component. Supports standard, compact, and animated variants.
class SuggestionChip extends StatefulWidget {
  const SuggestionChip({
    required this.text,
    super.key,
    this.onTap,
    this.compact = false,
    this.showIcon = true,
    this.icon,
    this.isOverflow = false,
    this.animated = true,
  });

  /// Creates a chip styled for welcome cards.
  const SuggestionChip.welcome({required this.text, super.key, this.onTap})
    : compact = false,
      showIcon = true,
      icon = Icons.chat_bubble_outline,
      isOverflow = false,
      animated = false;

  /// Creates a compact chip for tight spaces.
  const SuggestionChip.compact({
    required this.text,
    super.key,
    this.onTap,
    this.isOverflow = false,
  }) : compact = true,
       showIcon = false,
       icon = null,
       animated = false;

  /// The suggestion text to display.
  final String text;

  /// Called when the chip is tapped.
  final VoidCallback? onTap;

  /// Whether to use compact styling (smaller padding, text).
  final bool compact;

  /// Whether to show an icon before the text.
  final bool showIcon;

  /// The icon to display (defaults to lightbulb_outline for standard,
  /// chat_bubble_outline for welcome variant).
  final IconData? icon;

  /// Whether this chip represents overflow (e.g., "+3 more").
  /// Disables tap and uses muted styling.
  final bool isOverflow;

  /// Whether to animate on press (scale + color change).
  final bool animated;

  @override
  State<SuggestionChip> createState() => _SuggestionChipState();
}

class _SuggestionChipState extends State<SuggestionChip>
    with SingleTickerProviderStateMixin {
  AnimationController? _controller;
  Animation<double>? _scaleAnimation;
  bool _isPressed = false;

  @override
  void initState() {
    super.initState();
    if (widget.animated && !widget.isOverflow) {
      _controller = AnimationController(
        duration: const Duration(milliseconds: 100),
        vsync: this,
      );
      _scaleAnimation = Tween<double>(
        begin: 1,
        end: 0.95,
      ).animate(CurvedAnimation(parent: _controller!, curve: Curves.easeInOut));
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  void _onTapDown(TapDownDetails details) {
    if (!widget.animated || widget.isOverflow) return;
    setState(() => _isPressed = true);
    _controller?.forward();
  }

  void _onTapUp(TapUpDetails details) {
    if (!widget.animated || widget.isOverflow) return;
    setState(() => _isPressed = false);
    _controller?.reverse();
    widget.onTap?.call();
  }

  void _onTapCancel() {
    if (!widget.animated || widget.isOverflow) return;
    setState(() => _isPressed = false);
    _controller?.reverse();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.compact) {
      return _buildCompact(context);
    }
    if (widget.animated && _scaleAnimation != null) {
      return _buildAnimated(context);
    }
    return _buildSimple(context);
  }

  /// Compact variant - minimal styling.
  Widget _buildCompact(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return InkWell(
      onTap: widget.isOverflow ? null : widget.onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: widget.isOverflow
              ? colorScheme.surfaceContainerHighest
              : colorScheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(
          widget.text,
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
            color: widget.isOverflow
                ? colorScheme.onSurfaceVariant
                : colorScheme.onSurface,
          ),
        ),
      ),
    );
  }

  /// Simple variant - no animation (used in WelcomeCard).
  Widget _buildSimple(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final effectiveIcon = widget.icon ?? Icons.chat_bubble_outline;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: widget.onTap,
        borderRadius: BorderRadius.circular(20),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            color: colorScheme.surface,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: colorScheme.outline.withValues(alpha: 0.3),
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (widget.showIcon) ...[
                Icon(effectiveIcon, size: 14, color: colorScheme.primary),
                const SizedBox(width: 6),
              ],
              Flexible(
                child: Text(
                  widget.text,
                  style: Theme.of(
                    context,
                  ).textTheme.bodySmall?.copyWith(color: colorScheme.onSurface),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// Animated variant - scale and color on press.
  Widget _buildAnimated(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final effectiveIcon = widget.icon ?? Icons.lightbulb_outline;

    return ScaleTransition(
      scale: _scaleAnimation!,
      child: GestureDetector(
        onTapDown: _onTapDown,
        onTapUp: _onTapUp,
        onTapCancel: _onTapCancel,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 100),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            color: _isPressed
                ? colorScheme.primaryContainer
                : colorScheme.surfaceContainerLow,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: _isPressed
                  ? colorScheme.primary.withValues(alpha: 0.5)
                  : colorScheme.outline.withValues(alpha: 0.2),
            ),
            boxShadow: _isPressed
                ? null
                : [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.04),
                      blurRadius: 2,
                      offset: const Offset(0, 1),
                    ),
                  ],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (widget.showIcon) ...[
                Icon(
                  effectiveIcon,
                  size: 14,
                  color: _isPressed
                      ? colorScheme.primary
                      : colorScheme.onSurfaceVariant,
                ),
                const SizedBox(width: 6),
              ],
              Flexible(
                child: Text(
                  widget.text,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: _isPressed
                        ? colorScheme.onPrimaryContainer
                        : colorScheme.onSurface,
                    fontWeight: FontWeight.w500,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
