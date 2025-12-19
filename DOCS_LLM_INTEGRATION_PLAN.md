# Detailed Plan: Federated LLM Documentation

This document defines the strategy for generating isolated, domain-specific `llms.txt` files (Federated Documentation) to optimize context efficiency for AI agents.

## The Strategy: "Monolith to Federated"

We require separate documentation contexts for different tasks (e.g., "Server Backend" vs. "Flutter Frontend") to avoid token bloat. Since the `mkdocs-llmstxt` plugin only generates a single root file, we will implement a post-processing workflow.

### Workflow
1.  **Generate Monolith**: Configure `mkdocs-llmstxt` to generate a comprehensive `site/llms-full.txt` containing all project documentation (User, Server, Client).
2.  **Split & Distribute**: Run a custom script (`scripts/federate_llms_txt.py`) after the build. This script parses the monolith and extracts sections into dedicated files.

### Target Artifacts

We will generate the following isolated artifacts in the `site/` output:

1.  **`site/llms-project.txt` (User/Config Domain)**
    *   **Content**: Overview, Installation, Configuration, Architecture.
    *   **Use Case**: "How do I configure a new Room?" "What is the system architecture?"
2.  **`site/llms-server.txt` (Backend Domain)**
    *   **Content**: Python API definitions (fully expanded by `mkdocstrings`).
    *   **Use Case**: "Write a Python tool to query the RAG engine."
3.  **`site/llms-client.txt` (Frontend Domain)**
    *   **Content**: Flutter Widget index and selected Core API definitions.
    *   **Use Case**: "Create a new chat bubble widget."
4.  **`site/llms.txt` (Root Map)**
    *   **Content**: Links to the three domain files above.
    *   **Use Case**: Initial discovery and routing.

---

## Phase 1: Configuration (The Monolith)
**Goal**: Ensure `mkdocs` generates the raw material needed for all domains.
-   **Action**: Update `mkdocs.yml` `llmstxt` configuration.
-   **Settings**:
    -   `full_output: true` (Required to get the content for splitting).
    -   `sections`: explicit ordered list ensuring easy parsing (e.g., "Project Docs", "Server API", "Client API").

## Phase 2: The Federation Script
**Goal**: Create the tool that creates the isolated files.
-   **Action**: Create `scripts/federate_llms_txt.py`.
-   **Logic**:
    -   Read `site/llms-full.txt`.
    -   Regex match section headers (defined in Phase 1).
    -   Write matched content to `site/llms-{domain}.txt`.
    -   Generate a new root `site/llms.txt` that acts as a directory for these files.

## Phase 3: Documentation & Maintenance
**Goal**: Ensure developers understand how to maintain this pipeline.
-   **Action**: Update `docs/development/documentation.md`.
-   **Content**:
    -   Explain the "Federated" concept.
    -   Explain that `llms-full.txt` is an *intermediate* artifact, not the final product for agents.
    -   Guide on how to add new sections to the Federation Script if the docs structure changes.

## Phase 4: Integration
**Goal**: Automate the workflow.
-   **Action**: Update `scripts/verify_docs.sh`.
-   **Steps**:
    1.  Generate Dart Markdown.
    2.  Build MkDocs (generates Monolith).
    3.  Run Federation Script (splits Monolith).
    4.  Verify existence and size of `llms-server.txt`, `llms-client.txt`, etc.