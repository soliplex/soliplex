# Lessons Learned

Central index and criteria for capturing lessons from work sessions.

---

## What Qualifies as a Lesson?

| Qualifies | Does NOT Qualify |
|-----------|------------------|
| Discovered architectural constraint | Fixed a typo |
| Wrong initial approach that required rework | Normal debugging |
| Unexpected library/framework behavior | Expected test failure |
| Pattern that prevented a problem | Routine refactoring |
| Process that caused rework | Simple feature addition |
| Assumption that turned out to be wrong | Code that worked first try |

---

## Capture Triggers

Ask yourself these questions at the end of each session:

- "This took longer than expected because..."
- "We had to change approach when..."
- "A bug was caused by..."
- "The pattern from X would have helped here"
- "This assumption was wrong..."
- "I wish I had known that..."

If any of these apply, document a lesson.

---

## Lesson Format

Each lesson should include:

```markdown
## [Brief title]

- **Source:** SPEC:xxx or context
- **Context:** What were you trying to do?
- **Options:** (if applicable) What approaches were considered?
- **Lesson:** What did you learn?
- **Date:** YYYY-MM-DD
```

---

## Categories

| Category | File | When to Use |
|----------|------|-------------|
| architecture | `architecture.md` | Design patterns, code organization, system design |
| riverpod | `riverpod.md` | State management, providers, notifiers |
| testing | `testing.md` | Test patterns, mocking, coverage |
| flutter | `flutter.md` | Flutter-specific gotchas, widgets, platform |
| general | `general.md` | Catch-all for other insights |

---

## Current Lessons

### Architecture
- Observer pattern preferred for traffic inspection (2025-12-13)

### Riverpod
- Provider family for per-room state (2025-12-13)

### Testing
*(empty)*

### Flutter
*(empty)*

### General
*(empty)*

---

## Adding New Lessons

1. Identify the category from the table above
2. Open the corresponding `{category}.md` file
3. Add your lesson using the format above
4. Update the "Current Lessons" section in this README
5. Update `docs/INDEX.md` last-used date for the category file
