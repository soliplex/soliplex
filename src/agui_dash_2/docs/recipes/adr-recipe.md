# ADR Recipe

> Machine instructions for creating Architecture Decision Records.

## When to Use

- Choosing between multiple valid technical approaches
- Selecting a library, framework, or tool
- Defining a pattern that will be used repeatedly
- Making a tradeoff that future developers should understand
- Deprecating or reversing a previous decision

## When NOT to Use

- Obvious implementation details
- One-off code choices
- Decisions that don't affect architecture or future work

## File Location

`docs/adr/NNNN-{title}.md`

- NNNN: Zero-padded sequence number (0001, 0002, ...)
- title: Kebab-case summary (max 50 chars)

Example: `docs/adr/0012-tag-storage-format.md`

## Numbering

To find the next ADR number:
```bash
ls docs/adr/*.md 2>/dev/null | wc -l
```
Add 1, zero-pad to 4 digits.

## Template

```markdown
# ADR-{NNNN}: {Title}

| Field | Value |
|-------|-------|
| Status | proposed / accepted / deprecated / superseded |
| Date | YYYY-MM-DD |
| Deciders | {names or "team"} |
| Refs | SPEC:{name}, ADR-{NNNN} |

## Context

What is the issue? Why do we need to make a decision?

Keep this factual and objective. 2-4 sentences.

## Options Considered

### Option A: {Name}

Brief description.

- (+) Pro 1
- (+) Pro 2
- (-) Con 1

### Option B: {Name}

Brief description.

- (+) Pro 1
- (-) Con 1
- (-) Con 2

## Decision

We chose **Option {X}** because {primary reason}.

One paragraph max.

## Consequences

What becomes easier or harder because of this decision?

- (+) Positive consequence
- (-) Negative consequence / tradeoff
- (!) Risk to monitor
```

## Status Definitions

| Status | Meaning |
|--------|---------|
| proposed | Under discussion, not yet decided |
| accepted | Decision made and in effect |
| deprecated | No longer applies (explain why in Consequences) |
| superseded | Replaced by another ADR (link to it) |

## Linking

When creating an ADR:
1. Add `ADR-NNNN` to the Related section of the relevant spec
2. Add a work log entry noting the decision

When superseding:
1. Update old ADR status to `superseded`
2. Add "Superseded by ADR-NNNN" to old ADR's Consequences
3. Reference old ADR in new ADR's Refs

## Terse Format (for minor decisions)

For smaller decisions that still warrant documentation:

```markdown
# ADR-{NNNN}: {Title}

| Status | accepted | Date | YYYY-MM-DD | Refs | SPEC:{name} |

**Context**: {one sentence}

**Decision**: {one sentence}

**Consequence**: {one sentence}
```
