#!/bin/bash
# Build all apps in the monorepo

set -e

echo "=== Installing Python dependencies ==="
uv sync --all-packages

echo "=== Building Flutter Web ==="
cd apps/flutter-ui
flutter build web --release
cd ../..

echo "=== Building Ingester UI ==="
cd apps/ingester-ui
npm ci
npm run build
cd ../..

echo "=== All builds complete! ==="
