#!/bin/bash
# Generate Dart model classes from AG-UI feature JSON schemas
#
# This script uses quicktype to generate type-safe Dart classes from
# the JSON schemas in the schemas/ directory.
#
# Usage:
#   ./scripts/generate_dart_models.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Directories
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCHEMAS_DIR="$REPO_ROOT/schemas"
OUTPUT_DIR="$REPO_ROOT/src/flutter/lib/core/models/agui_features"

# Check if quicktype is installed
if ! command -v quicktype &> /dev/null; then
    echo -e "${RED}Error: quicktype is not installed${NC}"
    echo ""
    echo "quicktype is required to generate Dart classes from JSON schemas."
    echo ""
    echo -e "${YELLOW}To install quicktype:${NC}"
    echo ""
    echo "  Using npm (recommended):"
    echo "    npm install -g quicktype"
    echo ""
    echo "  Or using yarn:"
    echo "    yarn global add quicktype"
    echo ""
    echo -e "${YELLOW}For more information:${NC}"
    echo "  https://quicktype.io"
    echo ""
    exit 1
fi

echo -e "${GREEN}Generating Dart model classes...${NC}"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Generate Dart classes for each schema
for schema_file in "$SCHEMAS_DIR"/*.json; do
    # Skip if no JSON files found
    if [ ! -f "$schema_file" ]; then
        continue
    fi

    filename=$(basename "$schema_file" .json)

    # Convert snake_case to PascalCase for class name
    class_name=$(echo "$filename" | perl -pe 's/(^|_)([a-z])/\U$2/g')

    output_file="$OUTPUT_DIR/${filename}.dart"

    echo "Generating $output_file..."

    # Generate Dart class with quicktype
    # Options:
    #   --src-lang schema: Input files are JSON Schema format
    #   --null-safety: Generate null-safe Dart code
    #   --final-props: Make all properties final (immutable)
    # Note: --coders-in-class is OFF (default) to keep serialization code separate
    # Note: Nullability is inferred from JSON Schema (anyOf with null type)
    quicktype \
        --src "$schema_file" \
        --src-lang schema \
        --lang dart \
        --out "$output_file" \
        --top-level "$class_name" \
        --null-safety \
        --final-props

    echo -e "${GREEN}✓${NC} Generated $filename.dart"
done

echo ""
echo -e "${GREEN}Done!${NC} Dart models generated in:"
echo "  $OUTPUT_DIR"
echo ""
echo "Next steps:"
echo "  1. Review the generated models"
echo "  2. Add imports as needed"
echo "  3. Models include fromJson/toJson serialization methods"
