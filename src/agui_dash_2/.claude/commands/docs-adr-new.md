---
description: Create a new Architecture Decision Record
---

# Create New Architecture Decision Record

Help the user document a technical decision.

## Instructions

1. First, read `docs/recipes/adr-recipe.md` for the template and rules.

2. Count existing ADRs to determine next number:
   ```
   ls docs/adr/*.md 2>/dev/null | grep -v gitkeep | wc -l
   ```
   Next number = count + 1, zero-padded to 4 digits (0001, 0002, etc.)

3. Ask the user:
   - What decision needs to be made? (becomes Title)
   - What's the context? (why is this decision needed)
   - What options are being considered? (at least 2)
   - Which option do they prefer and why?
   - Is this related to a spec? (for cross-referencing)

4. Create the ADR at `docs/adr/NNNN-{title}.md`:
   - Set Status: accepted (or proposed if they're still deciding)
   - Set Date: today
   - Fill in Context, Options, Decision, Consequences

5. If related to a spec, update that spec's Related section to include the new ADR.

6. If there's an active work log for the related spec, add a note about the decision.

## ADR Naming

- Title should be short and descriptive
- Use kebab-case: "Tag Storage Format" → `0001-tag-storage-format.md`
