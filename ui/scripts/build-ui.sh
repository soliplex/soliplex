#!/bin/bash
set -e

echo "Building Soliplex Ingester UI..."

# Navigate to UI directory
cd ui

# Install dependencies
echo "Installing dependencies..."
npm install

# Build the UI
echo "Building production UI..."
npm run build

# Copy build artifacts to server static directory
echo "Copying build artifacts..."
mkdir -p ../src/soliplex/ingester/server/static
cp -r build/* ../src/soliplex/ingester/server/static/

echo "UI build complete!"
echo "UI artifacts copied to src/soliplex/ingester/server/static/"
