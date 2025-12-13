# Work Log Recipe

> Machine instructions for maintaining per-feature work logs.

## When to Use

- Starting a work session on a feature
- Completing a work session
- Any time code is modified for a tracked spec

## File Location

`docs/work-logs/{feature-name}.md`

Name MUST match the spec: `SPEC:room-tags` → `work-logs/room-tags.md`

## Template (New Log)

```markdown
# Work Log: {Feature Name}

| Field | Value |
|-------|-------|
| Spec | SPEC:{feature-name} |
| Created | YYYY-MM-DD |
| Status | active / complete |

---

## YYYY-MM-DD - Session 1

### Context
What was the goal of this session?

### Baseline Coverage
*Captured at start via `flutter test --coverage`*

| File | Coverage |
|------|----------|
| (none yet or existing coverage) | |

### Changes
- `path/to/file.dart`: Description of change
- `path/to/other.dart`: Description of change

### Decisions
- Chose X over Y because Z (see ADR-NNNN if applicable)

### Next
- [ ] Next action 1
- [ ] Next action 2

---
```

## Session Entry Template (Append)

```markdown
---

## YYYY-MM-DD - Session N

### Context
{goal}

### Changes
- `file`: {change}

### Decisions
- {decision or "None"}

### Lessons Learned
- [ ] None this session
OR
- **Lesson:** {brief description}
  - Context: {what happened}
  - Recommendation: {what to do differently}
  - Category: {architecture|riverpod|testing|flutter|general}

### Debt/Redesign Candidates
- [ ] None discovered
OR
- Added DEBT:{name} to BACKLOG.md - {brief description}

### Next
- [ ] {action}

### Resume Context
**Modified files:**
- `path/to/file.dart:NN-MM` - brief description of change

**Quality metrics:**
- Tests: N passing, M failing *(blocks completion if failing)*
- Coverage: file.dart XX%→YY% *(tracked, warn if decreased)*
- Analyzer: N issues (or "clean") *(blocks completion if warnings/errors)*
- Formatter: N files changed (or "clean") *(warning only)*

**Next action:** Single most important next step

---
```

## Resume Context (Critical for Session Continuity)

The Resume Context section captures essential state for picking up work in a new session.

**Why it matters:**
- New sessions start with zero context
- File paths alone don't show *where* in the file you were working
- Test/coverage status shows project health at session end

**What to include:**

| Field | Content | How to Get It |
|-------|---------|---------------|
| Modified files | File path + line range + brief description | `git diff --stat`, editor "recent files" |
| Tests | Pass/fail count | `flutter test 2>&1 \| tail -1` |
| Coverage | Before→After for touched files | `flutter test --coverage`, lcov report |
| Analyzer | Issue count or "clean" | `flutter analyze` |
| Formatter | Files needing format or "clean" | `dart format --set-exit-if-changed .` |
| Next action | Single actionable step (not a list) | Most important "Next" item |

**Example:**
```markdown
### Resume Context
**Modified files:**
- `lib/core/network/http_transport.dart:142-168` - removed dead runAgent code
- `lib/core/network/network_transport_layer.dart` (new file)

**Quality metrics:**
- Tests: 291 passing, 0 failing *(blocks completion if failing)*
- Coverage: network_transport_layer.dart new→85% *(tracked, warn if decreased)*
- Analyzer: clean *(blocks completion if warnings/errors)*
- Formatter: clean *(warning only)*

**Next action:** Wire SSE through transport layer for inspector visibility
```

## Testing Session Template

Use this when documenting test creation/execution:

```markdown
---

## YYYY-MM-DD - Testing

### Context
Adding unit tests for {feature}.

### Tests Created
- `test/path/to/file_test.dart`: {X} tests for {component}
- `test/path/to/other_test.dart`: {Y} tests for {component}

### Test Results
- **Total tests**: {N}
- **All passing**: Yes/No
- **Command**: `flutter test {paths}`

### Coverage
| File | Coverage |
|------|----------|
| lib/path/to/file.dart | XX% |

### Next
- [ ] {remaining test work or "Testing complete"}

---
```

## Rules

1. **Append-only**: Never delete or modify previous entries
2. **Timestamp everything**: Use ISO 8601 (YYYY-MM-DD)
3. **Be concrete**: List actual files changed, not vague descriptions
4. **Link decisions**: Reference ADRs when created
5. **Track blockers**: Note what's blocking progress

## Session Start Checklist

1. Check spec status (should be IN_PROGRESS)
2. **Read previous session's Resume Context** for quick orientation
3. Review previous session's "Next" items
4. Add new session entry with Context

## Session End Checklist

1. List all files modified in Changes
2. Note any decisions made
3. **Check for Lessons Learned** (see `docs/lessons/README.md` for criteria):
   - Did this take longer than expected?
   - Did you change approach mid-work?
   - Was there unexpected behavior?
   - Check "None this session" or document the lesson
4. **Check for Technical Debt** discovered:
   - Did you notice code that needs redesign?
   - Did you add a workaround?
   - Check "None discovered" or add to `docs/BACKLOG.md`
5. Add Next items for future sessions
6. **Add Resume Context section** (critical for session continuity):
   - Run `flutter test` and capture pass/fail count
   - Run `flutter test --coverage` and note changes for touched files
   - Run `flutter analyze` and capture issue count (or "clean")
   - Run `dart format --set-exit-if-changed .` and note status
   - Note file:line ranges for key changes
   - State single most important next action
7. If feature complete:
   - Update log Status → complete
   - Add final summary entry
   - Update spec to DONE

## Pause Entry Template

```markdown
---

## YYYY-MM-DD - Paused

### Reason
{why pausing}

### State at Pause
- Last completed: {summary}
- Next planned: {from previous Next section}

---
```

## Resume Entry Template

```markdown
---

## YYYY-MM-DD - Resumed

### Context
Resuming work. {current focus}

### Changes
- (starting fresh this session)

---
```

## Final Entry Template (Feature Complete)

```markdown
---

## YYYY-MM-DD - Complete

### Summary
Brief summary of the entire implementation.

### Total Files Modified
- `file1.dart`
- `file2.dart`
- ...

### Tests
- `test/path/to/file_test.dart`: {X} tests
- `test/path/to/other_test.dart`: {Y} tests
- **Total**: {N} tests, all passing

### Coverage Delta
*Comparing baseline (start) to final (completion)*

| File | Before | After | Delta |
|------|--------|-------|-------|
| lib/path/to/file.dart | 0% | 85% | +85% |
| lib/path/to/other.dart | 45% | 78% | +33% |

### ADRs Created
- ADR-NNNN: {title} (or "None")

### Lessons Learned
- {insight}

---
```

## Lessons Aggregation

At spec completion, lessons from "Lessons Learned" are extracted and added to `docs/lessons/{category}.md`:

Categories: `riverpod`, `testing`, `architecture`, `flutter`, `general`

Format in lessons file:
```markdown
## {Lesson title}
- **Source:** SPEC:{spec-name}
- **Context:** {brief context}
- **Lesson:** {the insight}
- **Date:** YYYY-MM-DD
```

## Cross-Reference Format

When referencing in other docs:
- Full: `docs/work-logs/room-tags.md`
- Short: `LOG:room-tags`
