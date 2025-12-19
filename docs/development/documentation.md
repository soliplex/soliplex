# Documentation Generation Workflow

This document explains the process for generating and maintaining the unified documentation site for Soliplex, which includes both Python (Server) and Dart (Client) API references.

## Overview

The documentation site is built using [MkDocs](https://www.mkdocs.org/) with the [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) theme. It combines handwritten documentation (like this page) with auto-generated API documentation from source code comments.

- **Python (Server) Docs**: Generated using the [mkdocstrings](https://mkdocstrings.github.io/) plugin, which parses docstrings directly from the Python source code in `src/soliplex`.
- **Dart (Client) Docs**: Generated using the [dart_doc_markdown](https://pub.dev/packages/dart_doc_markdown) package, which parses Dartdoc comments from the Flutter source code in `src/flutter` and creates Markdown files.

## How to Regenerate Documentation

A single script handles the entire process. To regenerate all documentation and build the final site, run:

```bash
./scripts/verify_docs.sh
```

This script performs the following steps:

1.  **Generates Dart Markdown**: Runs `scripts/generate_dart_markdown.sh`, which uses `dart_doc_markdown` to create Markdown files for the Flutter client in `docs/reference/client_api/`.
2.  **Creates Dart API Index**: Runs `scripts/generate_client_api_index.py` to create a summary page (`index.md`) for the generated Dart documentation.
3.  **Builds the MkDocs Site**: Runs `uv run mkdocs build` to assemble the handwritten docs, the generated Dart docs, and the `mkdocstrings`-generated Python docs into a static website in the `site/` directory.

## Debugging the Process

If you encounter issues, you can debug the process by understanding the location of the source and generated files.

### Server API (Python)

- **Source**: Python docstrings within the `src/soliplex/` directory.
- **Handler**: The file `docs/reference/server_api.md` contains the `::: soliplex` directive. This tells `mkdocstrings` to scan the `soliplex` package and generate documentation.
- **Output**: Rendered directly to HTML during the `mkdocs build` process.

Here is the content of the handler file:
```markdown
# Server API

::: soliplex
```

### Client API (Dart/Flutter)

- **Source**: Dartdoc comments (e.g., `/// comment`) within the `src/flutter/lib/` directory.
- **Generation**: The `scripts/generate_dart_markdown.sh` script runs the generation tool.
- **Output**: A collection of Markdown files is created in the `docs/reference/client_api/` directory. These files are ignored by `git`.
- **Index**: The `scripts/generate_client_api_index.py` script creates an `index.md` file inside `docs/reference/client_api/` that provides a clickable list of all generated library docs.

Here is an example of what the generated `index.md` looks like:
```markdown
# Client API Reference

## Libraries

- [action_button_widget](action_button_widget/overview.md)
- [activity_status_config](activity_status_config/overview.md)
...
```

## Viewing the Live Site

To view the documentation site locally, run the MkDocs development server:

```bash
uv run mkdocs serve
```

This will start a local web server (usually at `http://127.0.0.1:8000`) that automatically rebuilds the site when you make changes to the documentation files.

## LLM Documentation Strategy

This project uses a **Federated Documentation** strategy to provide context-optimized files for AI agents. This prevents token bloat by separating domains (Server vs. Client) and depth (Discovery vs. Knowledge).

### Artifacts

The build process generates the following files in `site/`:

| Domain | Map (Discovery) | Content (Knowledge) | Use Case |
| :--- | :--- | :--- | :--- |
| **Root** | `llms.txt` | N/A | Entry point. Links to domain maps. |
| **Project** | `llms-project.txt` | `llms-project-full.txt` | Architecture, Setup, Config. |
| **Server** | `llms-server.txt` | `llms-server-full.txt` | Python Backend API & Tools. |
| **Client** | `llms-client.txt` | `llms-client-full.txt` | Flutter Widget Library. |

### Absolute URL Policy

The root `llms.txt` **must use absolute URLs** (e.g., `https://soliplex.github.io/soliplex/llms-project.txt`) for links to domain maps. This ensures the file is portable and works correctly when hosted on GitHub Pages or other sub-path deployments where root-relative links (`/llms-project.txt`) would break. The federation script handles this automatically using the `site_url` from `mkdocs.yml`.

### How it Works

1.  **Monolith Generation**: `mkdocs-llmstxt` generates a single `llms-full.txt` containing all sections.
2.  **Federation Script**: A post-build hook (`scripts/federate_llms_txt.py`) runs automatically.
3.  **Splitting**: The script parses the monolith and splits it into domain-specific files based on section headers defined in `mkdocs.yml`.
4.  **Curation (Client API)**: The script applies special logic to the Client Map (`llms-client.txt`):
    -   **Filters Noise**: Removes individual methods, properties, and constructors.
    -   **Excludes Tests**: Removes any file path containing `_test`, `test/`, or `Test`.
    -   **Categorizes**: Groups classes into semantic buckets (e.g., "UI Components", "Services & State", "Network & API") based on keyword heuristics defined in `categorize_path` within the script.

### Local vs. Remote Consumption

You can control how links are generated in the root `llms.txt` map to support different agent workflows using the `DOCS_MODE` environment variable:

1.  **Remote (Default)**: Generates absolute HTTP URLs (e.g., `https://.../llms-server.txt`). Ideal for online agents.
2.  **Local (`DOCS_MODE=local`)**: Generates absolute filesystem paths (e.g., `/Users/me/repo/site/llms-server.txt`). Ideal for local agents (Gemini CLI, Claude Desktop) to robustly find files on disk.
3.  **Relative (`DOCS_MODE=relative`)**: Generates relative paths (e.g., `llms-server.txt`). Useful for portable archives.

**Example: Building for Local Agents**
```bash
DOCS_MODE=local ./scripts/verify_docs.sh
```
This enables the agent to read `site/llms.txt` and immediately follow the absolute paths to the domain files.

### Maintenance

To add a new section to a specific domain:
1.  Add the markdown file to the corresponding section in `mkdocs.yml` under `llmstxt/sections`.
2.  Ensure the section header matches one of the keys in `scripts/federate_llms_txt.py` if you are adding a new top-level domain.

To adjust the **Client API Categories**:
-   Edit `categorize_path()` in `scripts/federate_llms_txt.py`. You can add specific keywords or hard-coded overrides for directory names.
