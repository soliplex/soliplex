import 'package:flutter/material.dart';

/// A horizontally scrollable row of suggestion chips.
///
/// Displays prompt suggestions that users can tap to auto-fill the input field.
/// Typically placed above the message input area.
class SuggestionChips extends StatelessWidget {
  final List<String> suggestions;
  final void Function(String suggestion)? onSuggestionTap;
  final EdgeInsetsGeometry padding;
  final bool showIcon;

  const SuggestionChips({
    super.key,
    required this.suggestions,
    this.onSuggestionTap,
    this.padding = const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
    this.showIcon = true,
  });

  @override
  Widget build(BuildContext context) {
    if (suggestions.isEmpty) {
      return const SizedBox.shrink();
    }

    return SizedBox(
      height: 56,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: padding,
        clipBehavior: Clip.none,
        itemCount: suggestions.length,
        separatorBuilder: (context, index) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          return _SuggestionChip(
            suggestion: suggestions[index],
            onTap: () => onSuggestionTap?.call(suggestions[index]),
            showIcon: showIcon,
          );
        },
      ),
    );
  }
}

class _SuggestionChip extends StatefulWidget {
  final String suggestion;
  final VoidCallback? onTap;
  final bool showIcon;

  const _SuggestionChip({
    required this.suggestion,
    this.onTap,
    this.showIcon = true,
  });

  @override
  State<_SuggestionChip> createState() => _SuggestionChipState();
}

class _SuggestionChipState extends State<_SuggestionChip>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _scaleAnimation;
  bool _isPressed = false;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 100),
      vsync: this,
    );
    _scaleAnimation = Tween<double>(
      begin: 1.0,
      end: 0.95,
    ).animate(CurvedAnimation(parent: _controller, curve: Curves.easeInOut));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _onTapDown(TapDownDetails details) {
    setState(() => _isPressed = true);
    _controller.forward();
  }

  void _onTapUp(TapUpDetails details) {
    setState(() => _isPressed = false);
    _controller.reverse();
    widget.onTap?.call();
  }

  void _onTapCancel() {
    setState(() => _isPressed = false);
    _controller.reverse();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return ScaleTransition(
      scale: _scaleAnimation,
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
              width: 1,
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
                  Icons.lightbulb_outline,
                  size: 14,
                  color: _isPressed
                      ? colorScheme.primary
                      : colorScheme.onSurfaceVariant,
                ),
                const SizedBox(width: 6),
              ],
              Flexible(
                child: Text(
                  widget.suggestion,
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

/// A compact variant of SuggestionChips for use in tight spaces.
class CompactSuggestionChips extends StatelessWidget {
  final List<String> suggestions;
  final void Function(String suggestion)? onSuggestionTap;
  final int maxVisible;

  const CompactSuggestionChips({
    super.key,
    required this.suggestions,
    this.onSuggestionTap,
    this.maxVisible = 3,
  });

  @override
  Widget build(BuildContext context) {
    if (suggestions.isEmpty) {
      return const SizedBox.shrink();
    }

    final visibleSuggestions = suggestions.take(maxVisible).toList();
    final remaining = suggestions.length - maxVisible;

    return Wrap(
      spacing: 6,
      runSpacing: 6,
      children: [
        ...visibleSuggestions.map((suggestion) {
          return _CompactChip(
            label: suggestion,
            onTap: () => onSuggestionTap?.call(suggestion),
          );
        }),
        if (remaining > 0)
          _CompactChip(
            label: '+$remaining more',
            isOverflow: true,
            onTap: null,
          ),
      ],
    );
  }
}

class _CompactChip extends StatelessWidget {
  final String label;
  final VoidCallback? onTap;
  final bool isOverflow;

  const _CompactChip({
    required this.label,
    this.onTap,
    this.isOverflow = false,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: isOverflow
              ? colorScheme.surfaceContainerHighest
              : colorScheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(
          label,
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
            color: isOverflow
                ? colorScheme.onSurfaceVariant
                : colorScheme.onSurface,
          ),
        ),
      ),
    );
  }
}
