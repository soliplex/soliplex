import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// SkillsCard widget for displaying a person's skills and proficiency levels.
///
/// Data schema:
/// {
///   "person_id": "u1",
///   "name": "John Smith",
///   "title": "Engineering Lead",
///   "skills": [
///     {"name": "Flutter", "level": 5},
///     {"name": "Python", "level": 4},
///     {"name": "AWS", "level": 3}
///   ],
///   "avatar_url": "https://..." (optional)
/// }
///
/// Skill levels: 1-5 (Beginner to Expert)
class SkillsCardWidget extends StatelessWidget {
  const SkillsCardWidget({
    required this.personId,
    required this.name,
    required this.title,
    required this.skills,
    super.key,
    this.avatarUrl,
    this.onEvent,
  });

  factory SkillsCardWidget.fromData(
    Map<String, dynamic> data,
    void Function(String, Map<String, dynamic>)? onEvent,
  ) {
    final skillsList = data['skills'] as List<dynamic>? ?? [];
    return SkillsCardWidget(
      personId: data['person_id'] as String? ?? '',
      name: data['name'] as String? ?? 'Unknown',
      title: data['title'] as String? ?? '',
      skills: skillsList.map((s) {
        final map = s as Map<String, dynamic>;
        return Skill(
          name: map['name'] as String? ?? '',
          level: (map['level'] as num?)?.toInt() ?? 1,
        );
      }).toList(),
      avatarUrl: data['avatar_url'] as String?,
      onEvent: onEvent,
    );
  }
  final String personId;
  final String name;
  final String title;
  final List<Skill> skills;
  final String? avatarUrl;
  final void Function(String, Map<String, dynamic>)? onEvent;

  String _copyableText() {
    final buffer = StringBuffer();
    buffer.writeln('$name - $title');
    buffer.writeln('Skills:');
    for (final skill in skills) {
      buffer.writeln('  ${skill.name}: ${_levelLabel(skill.level)}');
    }
    return buffer.toString();
  }

  void _copyToClipboard() {
    Clipboard.setData(ClipboardData(text: _copyableText()));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Header with avatar, name, and copy button
            Row(
              children: [
                CircleAvatar(
                  radius: 20,
                  backgroundColor: theme.colorScheme.primaryContainer,
                  child: Text(
                    name.isNotEmpty ? name[0].toUpperCase() : '?',
                    style: TextStyle(
                      color: theme.colorScheme.onPrimaryContainer,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SelectableText(
                        name,
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      SelectableText(
                        title,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.hintColor,
                        ),
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
            const SizedBox(height: 12),
            const Divider(height: 1),
            const SizedBox(height: 8),
            // Skills list
            ...skills.map(
              (skill) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    SizedBox(
                      width: 100,
                      child: SelectableText(
                        skill.name,
                        style: theme.textTheme.bodyMedium,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(child: _SkillLevelBar(level: skill.level)),
                    const SizedBox(width: 8),
                    SelectableText(
                      _levelLabel(skill.level),
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.hintColor,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _levelLabel(int level) {
    switch (level) {
      case 1:
        return 'Beginner';
      case 2:
        return 'Basic';
      case 3:
        return 'Intermediate';
      case 4:
        return 'Advanced';
      case 5:
        return 'Expert';
      default:
        return 'Unknown';
    }
  }
}

class _SkillLevelBar extends StatelessWidget {
  const _SkillLevelBar({required this.level});
  final int level;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      children: List.generate(5, (index) {
        final filled = index < level;
        return Expanded(
          child: Container(
            height: 8,
            margin: const EdgeInsets.symmetric(horizontal: 1),
            decoration: BoxDecoration(
              color: filled
                  ? theme.colorScheme.primary
                  : theme.colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(4),
            ),
          ),
        );
      }),
    );
  }
}

class Skill {
  // 1-5

  const Skill({required this.name, required this.level});
  final String name;
  final int level;
}
