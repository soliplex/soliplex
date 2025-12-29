---
description: Show active work and pending items
---

# Documentation Status Overview

Show the current state of documentation work.

## Instructions

1. Find all IN_PROGRESS specs in `docs/specs/`:
   - Read each file and check Status field
   - List any that are IN_PROGRESS or BLOCKED

2. Find active work logs in `docs/work-logs/`:
   - Read each file and check Status field
   - For active logs, show the last session entry's date and "Next" items

3. Find recent ADRs (proposed status) in `docs/adr/`:
   - List any ADRs with status "proposed" that need decisions

4. Check for stale work:
   - Any IN_PROGRESS spec with no work log entry in 7+ days

## Output Format

### Active Work
| Spec | Status | Last Activity | Next Actions |
|------|--------|---------------|--------------|

### Pending Decisions
| ADR | Title | Date Proposed |
|-----|-------|---------------|

### Warnings
- List any stale specs or orphaned work logs

If nothing is in progress, say "No active work. Use `/docs-start` to begin work on a spec."
