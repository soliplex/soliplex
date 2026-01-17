#!/bin/bash
# Generate Dart model classes from AG-UI feature JSON schemas
#
# This script extracts individual feature schemas from the combined
# schema.json file and uses quicktype to generate type-safe Dart classes.
#
# Prerequisites:
#   Run ./scripts/generate_feature_schemas.sh first to create schema.json
#
# Usage:
#   ./scripts/generate_dart_models.sh <target_directory>
#
# Arguments:
#   target_directory: Path where Dart model files will be generated

set -e

# Check for required argument
if [ $# -eq 0 ]; then
    echo -e "${RED}Error: Missing required argument${NC}" >&2
    echo ""
    echo "Usage: $0 <target_directory>"
    echo ""
    echo "Arguments:"
    echo "  target_directory: Path where Dart model files will be generated"
    echo ""
    echo "Example:"
    echo "  $0 src/flutter/lib/core/models/agui_features"
    echo ""
    exit 1
fi

TARGET_DIR="$1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if target directory exists
if [ ! -d "$TARGET_DIR" ]; then
    echo -e "${RED}Error: Target directory does not exist${NC}" >&2
    echo ""
    echo "The specified target directory does not exist:"
    echo "  $TARGET_DIR"
    echo ""
    echo -e "${YELLOW}Please create the directory first or specify an existing directory.${NC}"
    echo ""
    echo "Example:"
    echo "  mkdir -p $TARGET_DIR"
    echo "  $0 $TARGET_DIR"
    echo ""
    exit 1
fi

# Directories
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCHEMAS_DIR="$REPO_ROOT/schemas"
COMBINED_SCHEMA="$SCHEMAS_DIR/schema.json"
OUTPUT_DIR="$TARGET_DIR"

# Check if schema.json exists
if [ ! -f "$COMBINED_SCHEMA" ]; then
    echo -e "${RED}Error: schema.json not found${NC}"
    echo ""
    echo "The combined schema file does not exist at:"
    echo "  $COMBINED_SCHEMA"
    echo ""
    echo -e "${YELLOW}Generate the schema first by running:${NC}"
    echo "  ./scripts/generate_feature_schemas.sh"
    echo ""
    exit 1
fi

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

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${RED}Error: jq is not installed${NC}"
    echo ""
    echo "jq is required to extract schemas from the combined schema file."
    echo ""
    echo -e "${YELLOW}To install jq:${NC}"
    echo "  macOS: brew install jq"
    echo "  Ubuntu: sudo apt-get install jq"
    echo ""
    exit 1
fi

# Check if dart is installed
if ! command -v dart &> /dev/null; then
    echo -e "${RED}Error: dart is not installed${NC}"
    echo ""
    echo "dart is required to format the generated Dart code."
    echo ""
    echo -e "${YELLOW}To install Dart/Flutter:${NC}"
    echo "  Visit https://flutter.dev/docs/get-started/install"
    echo ""
    exit 1
fi

echo -e "${GREEN}Extracting individual feature schemas...${NC}"
echo ""

# Create temporary directory for individual schemas
TEMP_SCHEMAS_DIR="$SCHEMAS_DIR/temp"
mkdir -p "$TEMP_SCHEMAS_DIR"

# Extract individual feature schemas from the combined schema
jq -r '.properties | keys[]' "$COMBINED_SCHEMA" | while read feature_name; do
    echo "Extracting schema for $feature_name..."
    jq ".properties.\"$feature_name\"" "$COMBINED_SCHEMA" > "$TEMP_SCHEMAS_DIR/${feature_name}.json"
done

echo ""
echo -e "${GREEN}Generating Dart model classes...${NC}"
echo ""

# Generate Dart classes for each extracted schema
for schema_file in "$TEMP_SCHEMAS_DIR"/*.json; do
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
echo -e "${GREEN}Adding linter ignore directives...${NC}"
echo ""

# Add linter ignore directives to each generated file
for dart_file in "$OUTPUT_DIR"/*.dart; do
    if [ -f "$dart_file" ]; then
        # Add comprehensive ignore directives at the top of the file
        # Split across multiple lines to respect 80-char limit
        cat > "${dart_file}.tmp" <<'EOF'
// Generated code from quicktype - ignoring style issues
// ignore_for_file: sort_constructors_first
// ignore_for_file: prefer_single_quotes
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: argument_type_not_assignable
// ignore_for_file: unnecessary_ignore
// ignore_for_file: avoid_dynamic_calls
// ignore_for_file: inference_failure_on_untyped_parameter
// ignore_for_file: inference_failure_on_collection_literal

EOF
        cat "$dart_file" >> "${dart_file}.tmp"
        mv "${dart_file}.tmp" "$dart_file"
        echo "Added linter ignores to $(basename "$dart_file")"
    fi
done

echo ""
echo -e "${GREEN}Formatting generated Dart code...${NC}"
echo ""

# Format all generated Dart files
dart format "$OUTPUT_DIR"

# Clean up temporary schemas
rm -rf "$TEMP_SCHEMAS_DIR"

echo ""
echo -e "${GREEN}Done!${NC} Dart models generated in:"
echo "  $OUTPUT_DIR"
