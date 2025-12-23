---
description: Run a 3-agent debate (Claude, Gemini, Codex) on a topic
---

# Triad Debate

Run an isolated vote across all three agents on a decision or question.

**Requires materials review** - User must approve context before agents vote.
**Agent commands pre-approved** - codex/gemini execution doesn't need tool confirmation.

## Usage

```
/debate <question or topic>
```

## Instructions

1. **Present materials for review** before running the debate:
   ```
   ## Debate Materials

   **Question**: <the question being debated>

   **Context provided to agents**:
   - <bullet list of relevant context, files, or findings>
   - <that will be shared with all agents>

   **Proceed with debate?** [Yes/No]
   ```

   Wait for user confirmation before continuing.

2. **Format the debate prompt** for each agent:
   ```
   DEBATE: <user's question>
   Context: <any relevant context from conversation>
   Vote YES or NO with one sentence reason.
   ```

3. **Run agents in isolation** (they should not see each other's responses):

   **Codex:**
   ```bash
   codex exec "<debate prompt>"
   ```

   **Gemini:**
   ```bash
   gemini -o text "<debate prompt>"
   ```

   **Claude:** Vote directly (you are Claude)

4. **Tally results** in a table:
   ```
   | Agent  | Vote | Reason |
   |--------|------|--------|
   | Codex  | YES/NO | ... |
   | Gemini | YES/NO | ... |
   | Claude | YES/NO | ... |

   **Result: X-Y <outcome>**
   ```

5. **Announce winner** and any recommended action.

## Example

User: `/debate Should we add TypeScript to this Python project?`

Output:
| Agent  | Vote | Reason |
|--------|------|--------|
| Codex  | NO   | Python project should stay Python |
| Gemini | NO   | Adds complexity without clear benefit |
| Claude | NO   | Type hints in Python are sufficient |

**Result: 0-3 NO** - Do not add TypeScript.
