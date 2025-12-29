#!/bin/bash
#script using docker to build ui instead of locally installed npm
set -e

echo "Building Soliplex Ingester UI..."

# Navigate to UI directory


# Install dependencies
echo "Installing dependencies..."
docker run -it --rm -v "$(pwd):/app" -w /app node:lts-alpine npm install

# Build the UI
echo "Building production UI..."
docker run -it --rm -v "$(pwd):/app" -w /app node:lts-alpine npm run build
# Copy build artifacts to server static directory
echo "Copying build artifacts..."
rm -r ../src/soliplex/ingester/server/static/*
mkdir -p ../src/soliplex/ingester/server/static
cp -r build/* ../src/soliplex/ingester/server/static/

echo "UI build complete!"
echo "UI artifacts copied to src/soliplex/ingester/server/static/"
