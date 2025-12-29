---
description: Pause work on an IN_PROGRESS spec
---

# Pause a Specification

Shelve current work to allow starting something else.

## Instructions

1. Check for IN_PROGRESS specs:
   - Scan `docs/specs/` for files with Status: IN_PROGRESS
   - If none found: "No specs are currently IN_PROGRESS."
   - Stop here

2. If found, confirm with user:
   - "Pause work on SPEC:{name}?"
   - Ask for pause reason (brief, e.g., "blocked on API changes", "switching to urgent bug")

3. Update the spec file:
   - Change Status: IN_PROGRESS → PAUSED
   - Update the Updated date

4. Update the work log:
   - Add pause entry:
     ```markdown
     ---

     ## YYYY-MM-DD - Paused

     ### Reason
     {user's reason}

     ### State at Pause
     - Last completed: {summary of last session}
     - Next planned: {from previous Next section}

     ---
     ```
   - Keep work log Status: active (can resume)

5. Confirm to user:
   - "Paused SPEC:{name}"
   - "You can now start new work with `/docs-start`"
   - "Resume later by selecting this spec in `/docs-start`"

## Notes

- PAUSED specs can be resumed via `/docs-start`
- PAUSED does NOT block starting new work (unlike IN_PROGRESS)
- Multiple specs can be PAUSED simultaneously
