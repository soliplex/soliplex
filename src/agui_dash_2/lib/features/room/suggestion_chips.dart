import 'package:flutter/material.dart';

import '../chat/widgets/suggestion_chip.dart';

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
          return SuggestionChip(
            text: suggestions[index],
            onTap: () => onSuggestionTap?.call(suggestions[index]),
            showIcon: showIcon,
            animated: true,
          );
        },
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
          return SuggestionChip.compact(
            text: suggestion,
            onTap: () => onSuggestionTap?.call(suggestion),
          );
        }),
        if (remaining > 0)
          SuggestionChip.compact(
            text: '+$remaining more',
            isOverflow: true,
          ),
      ],
    );
  }
}
