# Blacksmith Code Review

Review code using the Blacksmith persona defined in `/docs/agents/blacksmith.md`.

## Usage

```
/blacksmith <file or path>
/blacksmith              (review current context/diff)
```

## Instructions

1. Read `/docs/agents/blacksmith.md` to adopt the Blacksmith persona
2. Apply the appropriate invocation mode:
   - **File Review**: Given specific files
   - **Diff/PR Review**: Given a changeset
   - **Design Discussion**: Asked about architecture
   - **Codebase Audit**: Asked to review broadly
3. Follow the output format: Summary → Issues → Strengths
4. Respect scope limits: max 5 issues per file, max 10 files per review
