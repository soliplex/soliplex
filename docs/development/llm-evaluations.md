# LLM Documentation Lifecycle & Evaluation

> **Dependency**: This feature requires `feat/federated-llm-docs` to be merged first.
> The evaluation framework builds on the federated llms.txt strategy.

## Overview

This document describes the evaluation and quality assurance strategy for LLM-optimized documentation. The goal is to ensure AI agents can effectively use the documentation to understand and work with the Soliplex codebase.

## Current State

| Area | Status | Details |
|------|--------|---------|
| Federation structure | ✅ Complete | 3 domains, maps + content, 96.4% token reduction |
| Structural validation | ✅ CI-checked | File existence, link integrity, context efficiency |
| Script tests | ✅ 57 tests | Federation mechanics covered |
| Agent guidance | ✅ Basic | CLAUDE.md and GEMINI.md have quick-access tables |
| Agent Comprehension | ✅ Implemented | 34 evaluation cases across Project, Server, and Client domains |

## Gaps to Address

### 1. Baseline Performance
- Establish initial pass rate scores for current question bank.
- Identify which specific questions fail and why.

### 2. No Coverage Analysis
- Are all public APIs documented?
- Code changes without doc updates go undetected

### 3. No Staleness Detection
- Docs can become outdated silently
- No tracking of code vs doc modification dates

---

## Evaluation Tiers

### Tier 1: Structural (Exists)
- ✅ File existence
- ✅ Link integrity
- ✅ Context efficiency thresholds

### Tier 2: Comprehension Eval (Priority)
**Goal**: Verify agents can actually use the docs

**How it works**:
1. Define questions per domain with expected topics in `tests/evals/questions.yaml`
2. Feed question + relevant llms file to LLM API via `scripts/eval_comprehension.py`
3. Check if response mentions expected topics
4. Score pass/fail rates, track regression

**Schedule**: Weekly automated CI job

### Tier 3: Coverage Metrics
**Goal**: Visibility into documentation gaps

- Count documented items per domain
- Report percentage (informational only, non-blocking)

---

## Implementation

### Core Files

| File | Purpose |
|------|---------|
| `tests/evals/questions.yaml` | Eval question bank (34 cases) |
| `scripts/eval_comprehension.py` | LLM comprehension testing script |
| `.github/workflows/docs-eval.yml` | Weekly scheduled eval job |

### Question Format

```yaml
project:
  - id: "unique-slug"
    question: "How do I configure OIDC authentication?"
    expected_topics: ["OIDC", "client_id", "discovery_url"]
    source_file: "llms-project-full.txt"
```

### Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Context efficiency | 96.4% | >85% |
| Link integrity | 100% | 100% |
| Comprehension eval pass | Pending | >80% |
| Eval questions per domain | ~11 | 10-15 |

---

## Example Questions

### Project Domain
- "How do I configure OIDC authentication?"
- "What environment variables are required to run the server?"
- "How do I set up RAG with document ingestion?"

### Server Domain
- "What agents are available and what do they do?"
- "How do I add a new tool for agents to use?"
- "What API endpoints handle chat completions?"

### Client Domain
- "How does RoomService connect to the backend?"
- "What widgets are available for displaying chat messages?"
- "How is authentication state managed in the app?"

---

## Quality Checklist (Run Quarterly)

- [ ] Can I explain what each domain does from maps alone?
- [ ] Can I find API for 5 common tasks?
- [ ] Are code examples runnable?
- [ ] Is categorization still accurate?
- [ ] Do comprehension eval pass rates meet targets?

---

## Adding New Eval Questions

1. Identify a common task or question agents should handle
2. Add to `tests/evals/questions.yaml` under appropriate domain
3. Include 3-5 expected topics that a correct answer should mention
4. Run eval locally: `uv run python scripts/eval_comprehension.py`
5. Commit if pass rate is acceptable
