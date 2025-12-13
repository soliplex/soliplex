# Spec Recipe

> Machine instructions for creating and updating feature specifications.

## When to Use

- User describes a new feature to implement
- Starting work on a planned feature
- Updating requirements mid-implementation
- Completing a feature

## File Location

`docs/specs/{feature-name}.md`

Use kebab-case for naming: `room-tags.md`, `user-authentication.md`

## Template

```markdown
# SPEC: {Title}

| Field | Value |
|-------|-------|
| ID | SPEC:{kebab-name} |
| Status | PLANNED / IN_PROGRESS / PAUSED / DONE / BLOCKED |
| Created | YYYY-MM-DD |
| Updated | YYYY-MM-DD |
| Version | 0.1.0 |
| Author | {name} |

## Summary

One paragraph describing the feature and its value.

## Requirements

Checklist of concrete deliverables:

- [ ] Requirement 1
- [ ] Requirement 2
- [ ] Requirement 3

## Acceptance Criteria

How we know it's done:

- [ ] AC1: User can {action} and sees {result}
- [ ] AC2: System handles {edge case} by {behavior}
- [ ] AC-TEST: Unit tests exist for new/modified code

## Non-Goals

What this feature explicitly does NOT include:

- Non-goal 1
- Non-goal 2

## Edge Cases

Known edge cases and expected behavior:

| Case | Expected Behavior |
|------|-------------------|
| Empty input | Show validation message |
| Network failure | Retry with exponential backoff |

## Dependencies

- External: {API, service, etc.}
- Internal: SPEC:{other-feature}

## Related

- ADRs: {ADR-NNNN, ...} or "none yet"
- Work Log: LOG:{feature-name}

---

## Completion Record

*Fill in when status → DONE*

| Field | Value |
|-------|-------|
| Completed | YYYY-MM-DD |
| Final Version | 1.0.0 |

### Files Modified

- `path/to/file1.dart`
- `path/to/file2.dart`

### Tests

- `test/path/to/file1_test.dart`
- `test/path/to/file2_test.dart`

### Coverage

| File | Before | After | Delta |
|------|--------|-------|-------|
| path/to/file1.dart | 0% | 85% | +85% |

### Notes

Any implementation notes, gotchas, or follow-up considerations.
```

## Status Transitions

### PLANNED → IN_PROGRESS
1. Update `Status` field
2. Update `Updated` date
3. Create corresponding work log: `docs/work-logs/{feature-name}.md`

### IN_PROGRESS → DONE
1. Update `Status` field
2. Update `Updated` date
3. Increment `Version` to `1.0.0` (or appropriate)
4. Fill in Completion Record section
5. Check all Requirements and Acceptance Criteria boxes
6. Add final work log entry

### IN_PROGRESS → PAUSED
1. Update `Status` field
2. Update `Updated` date
3. Add pause entry to work log (reason, state at pause)

### PAUSED → IN_PROGRESS (resume)
1. Update `Status` field
2. Update `Updated` date
3. Add resume entry to work log

### Any → BLOCKED
1. Update `Status` field
2. Add blocking reason to work log
3. Note what's needed to unblock

## Checklist Syntax

- `[ ]` - Not started
- `[~]` - In progress (optional, for large items)
- `[x]` - Complete
