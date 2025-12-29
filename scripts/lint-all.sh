#!/bin/bash
# Run linters across the monorepo

set -e

echo "=== Linting Python apps ==="
uv run ruff check apps/soliplex apps/ingester apps/agents

echo "=== Linting Flutter ==="
cd apps/flutter-ui
flutter analyze
cd ../..

echo "=== Linting Node/Svelte ==="
cd apps/ingester-ui
npm run lint
cd ../..

echo "=== All linting passed! ==="
