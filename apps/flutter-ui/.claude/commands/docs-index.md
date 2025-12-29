---
description: Show document usage and staleness
---

# Document Index Report

Display documentation usage statistics and identify stale documents.

## Instructions

1. Read `docs/INDEX.md` to get all tracked documents with last-used dates

2. Calculate staleness for each document:
   - **Active** (<30 days old): No flag
   - **Review** (30-90 days old): Flag with warning
   - **Stale** (>90 days old): Flag for removal consideration

3. Sort documents by last-used date (oldest first)

4. Display report in sections:

   ```
   # Documentation Index Report
   Generated: YYYY-MM-DD

   ## Stale Documents (>90 days)
   Consider removing or updating these:

   | Document | Last Used | Age |
   |----------|-----------|-----|
   | NETWORK.md | 2025-09-01 | 104 days |

   ## Review Candidates (30-90 days)
   May need attention:

   | Document | Last Used | Age |
   |----------|-----------|-----|
   | DESIGN.md | 2025-11-01 | 43 days |

   ## Active Documents (<30 days)
   Recently used:

   | Document | Last Used | Age |
   |----------|-----------|-----|
   | CLAUDE.md | 2025-12-13 | 0 days |

   ## Summary
   - Total documents: {N}
   - Active: {N} ({%})
   - Review candidates: {N} ({%})
   - Stale: {N} ({%})
   ```

5. If stale documents found, suggest actions:
   ```
   Suggested actions for stale documents:
   - NETWORK.md: Consider merging into SOLIPLEX.md or removing
   - OLD-PLAN.md: Archive or delete if no longer relevant
   ```

6. Offer to update INDEX.md if any discrepancies found:
   - New .md files not in index
   - Files in index that no longer exist

## Staleness Rules

| Age | Status | Action |
|-----|--------|--------|
| <30 days | Active | None needed |
| 30-90 days | Review | Check if still relevant |
| >90 days | Stale | Consider removal/update |

## Updating Last-Used Dates

When you read a document for reference:
1. Note the document path
2. Update its "Last Used" date in `docs/INDEX.md`

This happens automatically during:
- `/docs-start` (spec and work log)
- `/docs-complete` (spec, work log, lessons, ADRs)
- Any time a doc is read for reference

## Finding Unlisted Documents

To check for .md files not in INDEX.md:

```bash
find . -name "*.md" -not -path "./ios/*" -not -path "./macos/*" -not -path "./.dart_tool/*"
```

Compare against INDEX.md entries and add any missing.
