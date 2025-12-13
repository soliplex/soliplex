---
description: Add a work log entry for current session
---

# Add Work Log Entry

Manually add a session entry to an active work log.

## Instructions

1. First, read `docs/recipes/work-log-recipe.md` for the session template.

2. Find active work logs:
   - Scan `docs/work-logs/` for files with Status: active
   - Present them to user if multiple exist

3. If no active work logs:
   - Tell user "No active work logs. Use `/docs-start` to begin work on a spec first."
   - Stop here

4. Gather session information from user:
   - What was the goal/context of this session?
   - What files were changed? (can also infer from git status)
   - Any decisions made? (reference ADRs if applicable)
   - What's next?

5. Append session entry to the work log:
   - Use today's date
   - Increment session number
   - Fill in Context, Changes, Decisions, Next sections

6. Confirm:
   - "Added session entry to LOG:{name}"
   - Show the entry that was added

## Auto-Detection

If only one work log is active, use it automatically without asking.

You can also check `git diff --name-only` to help populate the Changes section with actual files modified.

## When to Use

- End of a work session
- After making significant progress
- When switching to a different task
- Before taking a break
