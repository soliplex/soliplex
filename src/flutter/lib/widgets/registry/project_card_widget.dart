import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// ProjectCard widget for displaying project info with required skills.
///
/// Data schema:
/// {
///   "id": "p1",
///   "title": "Mobile App Redesign",
/// "description": "Complete overhaul of the customer-facing mobile
/// application",
///   "required_skills": ["Flutter", "Dart", "Figma"],
///   "status": "open" | "in_progress" | "completed",
/// "matched_skills": ["Flutter", "Dart"] (optional - skills that match a
/// candidate)
/// }
class ProjectCardWidget extends StatelessWidget {
  const ProjectCardWidget({
    required this.id,
    required this.title,
    required this.description,
    required this.requiredSkills,
    required this.status,
    super.key,
    this.matchedSkills,
    this.onEvent,
  });

  factory ProjectCardWidget.fromData(
    Map<String, dynamic> data,
    void Function(String, Map<String, dynamic>)? onEvent,
  ) {
    final skills = data['required_skills'] as List<dynamic>? ?? [];
    final matched = data['matched_skills'] as List<dynamic>?;
    return ProjectCardWidget(
      id: data['id'] as String? ?? '',
      title: data['title'] as String? ?? 'Untitled Project',
      description: data['description'] as String? ?? '',
      requiredSkills: skills.map((s) => s.toString()).toList(),
      status: data['status'] as String? ?? 'open',
      matchedSkills: matched?.map((s) => s.toString()).toList(),
      onEvent: onEvent,
    );
  }
  final String id;
  final String title;
  final String description;
  final List<String> requiredSkills;
  final String status;
  final List<String>? matchedSkills;
  final void Function(String, Map<String, dynamic>)? onEvent;

  String _copyableText() {
    final buffer = StringBuffer();
    buffer.writeln('$title ($status)');
    buffer.writeln(description);
    buffer.writeln('Required Skills: ${requiredSkills.join(", ")}');
    if (matchedSkills != null && matchedSkills!.isNotEmpty) {
      buffer.writeln('Matched Skills: ${matchedSkills!.join(", ")}');
    }
    return buffer.toString();
  }

  void _copyToClipboard() {
    Clipboard.setData(ClipboardData(text: _copyableText()));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final matchCount = matchedSkills?.length ?? 0;
    final totalRequired = requiredSkills.length;
    final hasMatches = matchedSkills != null && matchedSkills!.isNotEmpty;

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Header with title, status, and copy button
            Row(
              children: [
                Icon(
                  Icons.folder_outlined,
                  color: theme.colorScheme.primary,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: SelectableText(
                    title,
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                _StatusChip(status: status),
                IconButton(
                  icon: const Icon(Icons.copy, size: 18),
                  onPressed: _copyToClipboard,
                  tooltip: 'Copy to clipboard',
                  visualDensity: VisualDensity.compact,
                ),
              ],
            ),
            const SizedBox(height: 8),
            // Description
            SelectableText(
              description,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.hintColor,
              ),
              maxLines: 2,
            ),
            const SizedBox(height: 12),
            // Required skills
            SelectableText(
              'Required Skills:',
              style: theme.textTheme.labelMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 4,
              children: requiredSkills.map((skill) {
                final isMatched = matchedSkills?.contains(skill) ?? false;
                return Chip(
                  label: Text(
                    skill,
                    style: TextStyle(
                      fontSize: 12,
                      color: isMatched
                          ? theme.colorScheme.onPrimary
                          : theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  backgroundColor: isMatched
                      ? theme.colorScheme.primary
                      : theme.colorScheme.surfaceContainerHighest,
                  padding: EdgeInsets.zero,
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  visualDensity: VisualDensity.compact,
                );
              }).toList(),
            ),
            // Match indicator if we have matched skills
            if (hasMatches) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: theme.colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.check_circle,
                      size: 16,
                      color: theme.colorScheme.primary,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '$matchCount/$totalRequired skills matched',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.primary,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status});
  final String status;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    Color bgColor;
    Color textColor;
    String label;

    switch (status) {
      case 'open':
        bgColor = Colors.green.shade100;
        textColor = Colors.green.shade800;
        label = 'Open';
      case 'in_progress':
        bgColor = Colors.orange.shade100;
        textColor = Colors.orange.shade800;
        label = 'In Progress';
      case 'completed':
        bgColor = Colors.grey.shade200;
        textColor = Colors.grey.shade700;
        label = 'Completed';
      default:
        bgColor = theme.colorScheme.surfaceContainerHighest;
        textColor = theme.colorScheme.onSurfaceVariant;
        label = status;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w500,
          color: textColor,
        ),
      ),
    );
  }
}
