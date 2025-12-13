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

5. **Capture Resume Context** (critical for session continuity):
   - Run `flutter test` and capture pass/fail count
   - Run `flutter test --coverage` and note coverage for touched files
   - Run `flutter analyze` and capture issue count (or "clean")
   - Run `dart format --set-exit-if-changed .` and note status (or "clean")
   - Run `git diff --stat` to get file change ranges
   - Ask: "What's the single most important next action?"

   **Quality Gate Warnings:**
   - If tests are failing:
     - Show: "⚠️ Tests failing - these will BLOCK `/docs-complete`"
   - If coverage decreased for modified files:
     - Show: "⚠️ Coverage decreased for {files} - review before completion"
   - If `flutter analyze` reports warnings or errors:
     - Show: "⚠️ Analyzer has {N} warnings/errors - these will BLOCK `/docs-complete`"
     - List the issues
   - If `dart format --set-exit-if-changed` fails:
     - Show: "⚠️ {N} files need formatting - run `dart format .` to fix"

6. Append session entry to the work log:
   - Use today's date
   - Increment session number
   - Fill in Context, Changes, Decisions, Next sections
   - **Include Resume Context section with quality metrics**

7. Confirm:
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
