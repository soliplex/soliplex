#!/bin/bash
set -e

# Default to absolute mode (filesystem paths) for agent convenience
export DOCS_MODE="${DOCS_MODE:-absolute}"

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Generating Dart Markdown docs..."
"$PROJECT_ROOT/scripts/generate_dart_markdown.sh"

echo "✅ Dart Markdown docs generated in docs/reference/client_api"

echo "Augmenting Dart docs with API links..."
python3 "$PROJECT_ROOT/scripts/augment_dart_docs.py"

echo "Generating Client API Index..."
python3 "$PROJECT_ROOT/scripts/generate_client_api_index.py"

echo "Building MkDocs site..."
cd "$PROJECT_ROOT"
uv run mkdocs build

echo "✅ MkDocs site built successfully in site/"
echo "   - Server API: site/reference/server_api/index.html"
echo "   - Client API: site/reference/client_api/index.html"

echo "Validating federation strategy..."
uv run python "$PROJECT_ROOT/scripts/validate_llms_strategy.py"
if [ $? -ne 0 ]; then
    echo "❌ Federation validation failed!"
    exit 1
fi

echo "✅ Documentation build complete!"
