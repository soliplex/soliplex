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
