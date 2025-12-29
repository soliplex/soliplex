#!/bin/bash
# Run all tests across the monorepo

set -e

echo "=== Testing Soliplex App ==="
cd apps/soliplex
uv run pytest tests/unit
cd ../..

echo "=== Testing Ingester App ==="
cd apps/ingester
uv run pytest tests/unit
cd ../..

echo "=== Testing Agents App ==="
cd apps/agents
uv run pytest tests/unit
cd ../..

echo "=== Testing Flutter UI ==="
cd apps/flutter-ui
flutter test
cd ../..

echo "=== All tests passed! ==="
