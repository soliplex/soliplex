#!/bin/bash
# Coverage enforcement script for soliplex
# Senior Testing Agent requirement: Minimum 85% line coverage, 80% branch coverage

set -e

# Configuration
MIN_LINE_COVERAGE=85
MIN_BRANCH_COVERAGE=80
COVERAGE_DIR="coverage"
LCOV_FILE="$COVERAGE_DIR/lcov.info"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================"
echo "Running Flutter tests with coverage..."
echo "================================================"

# Run tests with coverage
flutter test --coverage

# Check if lcov.info was generated
if [ ! -f "$LCOV_FILE" ]; then
    echo -e "${RED}ERROR: Coverage file not found at $LCOV_FILE${NC}"
    exit 1
fi

echo ""
echo "================================================"
echo "Analyzing coverage..."
echo "================================================"

# Extract line coverage using lcov
if command -v lcov &> /dev/null; then
    # Generate summary
    SUMMARY=$(lcov --summary "$LCOV_FILE" 2>&1)

    # Extract line coverage percentage
    LINE_COVERAGE=$(echo "$SUMMARY" | grep "lines" | sed 's/.*: \([0-9.]*\)%.*/\1/')

    # Extract branch coverage if available
    BRANCH_LINE=$(echo "$SUMMARY" | grep "branches" || echo "")
    if [ -n "$BRANCH_LINE" ]; then
        BRANCH_COVERAGE=$(echo "$BRANCH_LINE" | sed 's/.*: \([0-9.]*\)%.*/\1/')
    else
        BRANCH_COVERAGE="N/A"
    fi
else
    # Fallback: parse lcov.info manually
    TOTAL_LINES=$(grep -c "^DA:" "$LCOV_FILE" || echo "0")
    COVERED_LINES=$(grep "^DA:" "$LCOV_FILE" | grep -v ",0$" | wc -l | tr -d ' ')

    if [ "$TOTAL_LINES" -gt 0 ]; then
        LINE_COVERAGE=$(echo "scale=1; $COVERED_LINES * 100 / $TOTAL_LINES" | bc)
    else
        LINE_COVERAGE="0"
    fi
    BRANCH_COVERAGE="N/A"
fi

echo ""
echo "Coverage Results:"
echo "  Line coverage:   ${LINE_COVERAGE}% (minimum: ${MIN_LINE_COVERAGE}%)"
echo "  Branch coverage: ${BRANCH_COVERAGE}% (minimum: ${MIN_BRANCH_COVERAGE}%)"
echo ""

# Check line coverage threshold
FAILED=0

if [ "$LINE_COVERAGE" != "N/A" ]; then
    LINE_INT=$(echo "$LINE_COVERAGE" | cut -d. -f1)
    if [ "$LINE_INT" -lt "$MIN_LINE_COVERAGE" ]; then
        echo -e "${RED}FAIL: Line coverage ${LINE_COVERAGE}% is below minimum ${MIN_LINE_COVERAGE}%${NC}"
        FAILED=1
    else
        echo -e "${GREEN}PASS: Line coverage ${LINE_COVERAGE}% meets minimum ${MIN_LINE_COVERAGE}%${NC}"
    fi
fi

# Check branch coverage threshold (if available)
if [ "$BRANCH_COVERAGE" != "N/A" ]; then
    BRANCH_INT=$(echo "$BRANCH_COVERAGE" | cut -d. -f1)
    if [ "$BRANCH_INT" -lt "$MIN_BRANCH_COVERAGE" ]; then
        echo -e "${RED}FAIL: Branch coverage ${BRANCH_COVERAGE}% is below minimum ${MIN_BRANCH_COVERAGE}%${NC}"
        FAILED=1
    else
        echo -e "${GREEN}PASS: Branch coverage ${BRANCH_COVERAGE}% meets minimum ${MIN_BRANCH_COVERAGE}%${NC}"
    fi
fi

echo ""

# Generate HTML report if genhtml is available
if command -v genhtml &> /dev/null; then
    echo "Generating HTML coverage report..."
    genhtml "$LCOV_FILE" -o "$COVERAGE_DIR/html" --quiet
    echo -e "${GREEN}HTML report generated at: $COVERAGE_DIR/html/index.html${NC}"
fi

echo ""

if [ $FAILED -eq 1 ]; then
    echo -e "${RED}================================================${NC}"
    echo -e "${RED}COVERAGE CHECK FAILED${NC}"
    echo -e "${RED}================================================${NC}"
    exit 1
else
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}COVERAGE CHECK PASSED${NC}"
    echo -e "${GREEN}================================================${NC}"
    exit 0
fi
