---
description: List all specs, ADRs, and work logs with status
---

# List All Documentation

Scan the docs/ directory and provide a status overview.

## Instructions

1. Read all files in `docs/specs/` and extract:
   - Filename
   - Status (PLANNED, IN_PROGRESS, DONE, BLOCKED)
   - Version
   - Last updated date

2. Read all files in `docs/adr/` and extract:
   - ADR number and title
   - Status (proposed, accepted, deprecated, superseded)
   - Date

3. Read all files in `docs/work-logs/` and extract:
   - Feature name
   - Status (active, complete)
   - Date of last entry

## Output Format

Present as three tables:

### Specs
| Name | Status | Version | Updated |
|------|--------|---------|---------|

### ADRs
| ID | Title | Status | Date |
|----|-------|--------|------|

### Work Logs
| Feature | Status | Last Entry |
|---------|--------|------------|

If any directory is empty, say "No {type} found."
