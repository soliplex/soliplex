#!/bin/bash
set -e
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Ensure output directory exists and is clean
rm -rf "$PROJECT_ROOT/docs/reference/client_api"
mkdir -p "$PROJECT_ROOT/docs/reference/client_api"

echo "Generating Dart Markdown docs..."

# Run dart_doc_markdown
# Usage: <project_directory> <output_directory>
dart pub global run dart_doc_markdown "$PROJECT_ROOT/src/flutter" "$PROJECT_ROOT/docs/reference/client_api"

echo "✅ Dart Markdown docs generated in docs/reference/client_api"

