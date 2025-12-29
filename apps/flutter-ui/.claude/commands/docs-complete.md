---
description: Mark a spec as DONE
---

# Complete a Specification

Mark a spec as DONE and add completion records.

## Instructions

1. List IN_PROGRESS specs:
   - Scan `docs/specs/` for files with Status: IN_PROGRESS
   - Present them to user to choose

2. If no IN_PROGRESS specs:
   - Tell user "No specs are currently IN_PROGRESS."
   - Stop here

3. Once user selects a spec to complete:

   a. **Check for testing work log entry**:
      - Read the work log for this spec
      - Look for a session entry that documents testing (tests created, test results)
      - If no testing documented: warn user and ask if they want to add tests first
      - This is a soft check (warn, don't block)

   b. **Quality Gate: Analyzer** (BLOCKING):
      - Run `flutter analyze`
      - Parse output for errors and warnings (ignore info-level hints)
      - Count issues: `flutter analyze 2>&1 | grep -cE " warning | error "`
      - If count > 0: **BLOCK completion**
        - Show: "❌ Cannot complete spec: {N} analyzer warnings/errors found"
        - List the issues
        - Instruct: "Fix these issues and run `/docs-complete` again"
        - Stop here - do not proceed
      - If clean: proceed to next step

   c. **Quality Gate: Formatter** (WARNING):
      - Run `dart format --set-exit-if-changed . 2>&1`
      - If exit code != 0: **WARN** (don't block)
        - Show: "⚠️ Warning: Some files need formatting"
        - Suggest: "Run `dart format .` to fix"
      - Proceed regardless of result

   d. **Quality Gate: Coverage** (WARNING):
      - Run `flutter test --coverage`
      - Compare coverage for modified files against baseline (from work log)
      - If coverage decreased for any file: **WARN** (don't block)
        - Show: "⚠️ Coverage decreased for: {files}"
        - Show before/after for each affected file
      - Proceed regardless of result

   e. **Auto-detect test files**:
      - Scan `test/` directory for files related to the spec
      - Match by: feature name, file names mentioned in work log
      - List discovered test files for inclusion in completion record

   f. **Record final coverage**:
      - Run `flutter test --coverage`
      - Parse `coverage/lcov.info`
      - Compare against baseline from work log (if recorded)
      - Calculate delta for files modified by this spec
      - Format as coverage table (see work-log-recipe for format)

   g. Review the spec:
      - Check all Requirements - are they done?
      - Check all Acceptance Criteria - are they met?
      - Verify quality ACs are satisfied (tests, analyzer, formatter, coverage)
      - If not all checked, ask user to confirm completion anyway or address remaining items

   h. Update the spec file:
      - Change Status: IN_PROGRESS → DONE
      - Update the Updated date
      - Change Version to 1.0.0 (or increment if already versioned)
      - Fill in Completion Record section:
        - Completed date
        - Final Version
        - Files Modified (infer from work log)
        - Tests (auto-detected test files)
        - Notes (any implementation notes)

   i. Update the work log:
      - Add final "Complete" entry using template from recipe
      - Include coverage delta table
      - Change work log Status: active → complete
      - Include summary, total files modified, ADRs created, lessons learned

   j. **ADR Wizard** (run after work log update):
      1. Extract all decisions from work log (### Decisions sections)
      2. Scan for keywords: "chose", "vs", "over", "instead of", "pattern", "architecture"
      3. For each flagged decision, show terse outline:
         ```
         Decision: {title}
         Context: {why this came up}
         Options: {what was considered}
         Outcome: {what was chosen and why}
         → Create ADR? [y/n]
         ```
      4. For each "yes", create ADR file using `docs/recipes/adr-recipe.md` template
      5. Link new ADRs in spec's Related section

   k. **Lessons Check** (PROMPT):
      1. Scan ALL work log sessions for "### Lessons Learned" sections
      2. Check if any sessions have uncategorized lessons (not yet in docs/lessons/)
      3. If ALL sessions say "None this session": prompt user
         ```
         No lessons documented across {N} sessions.
         Before completing, consider:
         - Did anything take longer than expected?
         - Did you change approach mid-work?
         - Any unexpected behavior discovered?

         Add lesson? [y/n]
         ```
      4. For any uncategorized lessons, ask user to categorize:
         - riverpod, testing, architecture, flutter, or general
      5. Append to `docs/lessons/{category}.md` with format:
         ```markdown
         ## {Lesson title}
         - **Source:** SPEC:{spec-name}
         - **Context:** {brief context}
         - **Lesson:** {the insight}
         - **Date:** YYYY-MM-DD
         ```
      6. Update `docs/lessons/README.md` "Current Lessons" section

   l. **Technical Debt Check**:
      1. Scan work log for "### Debt/Redesign Candidates" sections
      2. Verify any DEBT: items mentioned are in `docs/BACKLOG.md`
      3. Check spec for "## Technical Debt Discovered" section
      4. If debt discovered but not in BACKLOG: add it now
      5. If no debt sections found: prompt user
         ```
         No technical debt documented.
         Did you notice any code that should be redesigned?
         [y/n]
         ```

   m. **Update Document Index**:
      1. Update `docs/INDEX.md` last-used dates for:
         - The spec being completed
         - The work log
         - Any ADRs referenced
         - Any lessons files modified

   n. **Deferred Items Prompt**:
      1. Check work log for "Deferred Items" or unchecked "Next" items
      2. List them to user:
         ```
         Deferred items found:
         - [ ] Filter UI
         - [ ] Widget tests
         - [ ] Persistent storage

         Create PLANNED specs for any of these? [select or skip]
         ```
      3. For each selected, create minimal spec:
         - Title from item
         - Summary: "Follow-up from SPEC:{parent-spec}"
         - Status: PLANNED
         - Dependencies: SPEC:{parent-spec}

4. Confirm to user:
   - "Completed SPEC:{name} at version {version}"
   - "Work log finalized"
   - "Tests: {count} test files, {coverage}% coverage on touched files"
   - "ADRs created: {count or 'none'}"
   - "Lessons added: {count} to {categories}"
   - "Technical debt tracked: {count or 'none'}"
   - "Follow-up specs: {count or 'none'}"
   - "Document index updated"
   - Show summary of what was accomplished

## Version Guidelines

- First completion: 1.0.0
- If spec was previously completed and reopened: increment minor (1.1.0)
- Major version for significant scope changes

## Coverage Delta Format

Include in completion entry:
```markdown
### Coverage Delta
| File | Before | After | Delta |
|------|--------|-------|-------|
| lib/path/to/file.dart | 0% | 85% | +85% |
```
