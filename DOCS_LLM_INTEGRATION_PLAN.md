# Detailed Plan: Federated LLM Documentation

This document defines the strategy for generating isolated, domain-specific `llms.txt` files (Federated Documentation) to optimize context efficiency for AI agents.

## The Strategy: "Dual-Pass Federated Splitting"

We require separate documentation contexts for different tasks (e.g., "Server Backend" vs. "Flutter Frontend") to avoid token bloat. Furthermore, we must distinguish between **Discovery** (Map) and **Ingestion** (Content) within each domain.

### Workflow
1.  **Generate Monoliths**: Configure `mkdocs-llmstxt` to generate both `site/llms.txt` (the global map) and `site/llms-full.txt` (the global content).
2.  **Split & Distribute**: Run a custom script (`scripts/federate_llms_txt.py`) after the build. This script parses *both* monoliths.

### Target Artifacts

We will generate the following isolated artifacts in the `site/` output:

#### 1. Domain Maps (`llms-{domain}.txt`)
*   **Source**: Extracted from `site/llms.txt`.
*   **Content**: High-level index and links for that specific domain.
*   **Size**: Very small (~2KB).
*   **Use Case**: Agent checks this to find *which* specific file to read.

#### 2. Domain Content (`llms-{domain}-full.txt`)
*   **Source**: Extracted from `site/llms-full.txt`.
*   **Content**: Full text, expanded API definitions, and guides.
*   **Size**: Large (50KB+).
*   **Use Case**: Agent ingests this for deep reasoning or RAG.

#### 3. Root Discovery (`llms.txt`)
*   **Content**: Links to the Domain Maps (`llms-server.txt`, etc.).
*   **Use Case**: "Where do I start?"

---

## Phase 1: Configuration (The Monolith)
**Goal**: Ensure `mkdocs` generates the raw material needed for all domains.
-   **Action**: Update `mkdocs.yml` `llmstxt` configuration.
-   **Settings**:
    -   `full_output: llms-full.txt` (Required).
    -   `sections`: explicit ordered list (Project, Server, Client).

## Phase 2: The Federation Script
**Goal**: Create the tool that creates the isolated files.
-   **Action**: Create `scripts/federate_llms_txt.py`.
-   **Logic**:
    -   **Pass 1**: Read `site/llms.txt`. Split by section headers. Write to `site/llms-{domain}.txt`.
    -   **Pass 2**: Read `site/llms-full.txt`. Split by section headers. Write to `site/llms-{domain}-full.txt`.
    -   **Finalize**: Rewrite root `site/llms.txt` to point to the new Domain Maps.

## Phase 3: Documentation & Maintenance
**Goal**: Ensure developers understand how to maintain this pipeline.
-   **Action**: Update `docs/development/documentation.md`.
-   **Content**:
    -   Explain the "Federated" concept.
    -   Explain the "Map vs. Content" distinction.

## Phase 4: Integration
**Goal**: Automate the workflow.
-   **Action**: Update `scripts/verify_docs.sh`.
-   **Steps**:
    1.  Generate Dart Markdown.
    2.  Build MkDocs (generates Monoliths).
    3.  Run Federation Script (splits Monoliths).
    4.  Verify existence of maps and full files.
