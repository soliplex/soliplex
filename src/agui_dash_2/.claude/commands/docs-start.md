---
description: Start or resume work on a spec
---

# Start Work on a Specification

Start a PLANNED spec or resume a PAUSED spec.

## Instructions

1. First, read `docs/recipes/work-log-recipe.md` for the template.

2. **SINGLE SPEC ENFORCEMENT** (do this BEFORE anything else):
   - Scan `docs/specs/` for any files with Status: IN_PROGRESS
   - If found: STOP and tell user:
     "Cannot start a new spec. SPEC:{active-spec-name} is already IN_PROGRESS."
     "Complete or pause that spec first using `/docs-complete` or `/docs-pause`."
   - Do NOT proceed. Do NOT offer overrides. This is a hard rule.
   - Note: PAUSED specs do NOT block - only IN_PROGRESS blocks.

3. List available specs:
   - Scan `docs/specs/` for files with Status: PLANNED or PAUSED
   - Present them grouped:
     ```
     PAUSED (can resume):
     - SPEC:feature-x (paused: blocked on API)

     PLANNED (new work):
     - SPEC:feature-y
     - SPEC:feature-z
     ```

4. If no PLANNED or PAUSED specs exist:
   - Tell user "No specs available. Use `/docs-spec-new` to create one first."
   - Stop here

5. Once user selects a spec:

   **If PAUSED (resuming):**

   a. Update the spec file:
      - Change Status: PAUSED → IN_PROGRESS
      - Update the Updated date

   b. Add resume entry to existing work log:
      ```markdown
      ---

      ## YYYY-MM-DD - Resumed

      ### Context
      Resuming work. {ask user for current focus}

      ### Changes
      - (starting fresh this session)

      ---
      ```

   c. Confirm: "Resumed SPEC:{name}"

   **If PLANNED (new work):**

   a. Update the spec file:
      - Change Status: PLANNED → IN_PROGRESS
      - Update the Updated date to today

   b. **Capture baseline coverage**:
      - Run `flutter test --coverage` (may take a moment)
      - Parse `coverage/lcov.info` if it exists
      - Note: baseline may be empty for new features

   c. Create work log at `docs/work-logs/{spec-name}.md`:
      - Use template from recipe
      - Set Spec reference
      - Set Created date
      - Set Status: active
      - Add first session entry with Context from user (ask what they're starting with)
      - Include baseline coverage section (see recipe for format)

   d. Confirm to user:
      - "Started work on SPEC:{name}"
      - "Work log created at docs/work-logs/{name}.md"
      - "Baseline coverage captured"

## Important

- Spec name and work log name must match exactly
- Only ONE spec can be IN_PROGRESS at a time (PAUSED does not block)
- Multiple specs can be PAUSED simultaneously
