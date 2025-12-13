---
description: Create a new feature specification
---

# Create New Specification

Help the user create a new feature specification.

## Instructions

1. First, read `docs/recipes/spec-recipe.md` for the template and rules.

2. Ask the user for:
   - Feature name (will become filename in kebab-case)
   - Brief summary (1-2 sentences)
   - Key requirements (can be rough, you'll help refine)

3. Create the spec file at `docs/specs/{feature-name}.md` using the full template from the recipe:
   - Set Status: PLANNED
   - Set Created: today's date
   - Set Version: 0.1.0
   - Fill in Summary from user input
   - Convert requirements to checklist format
   - Add reasonable Acceptance Criteria based on requirements
   - Add Non-Goals section (ask user or leave with placeholder)
   - Add Edge Cases table (populate obvious ones)
   - Leave Related section with "ADRs: none yet"

4. Show the user the created spec and ask if they want to refine anything.

## Important

- Use kebab-case for filename: "Room Tags" → `room-tags.md`
- ID format: `SPEC:room-tags`
- Don't create work log yet - that happens with `/docs-start`
