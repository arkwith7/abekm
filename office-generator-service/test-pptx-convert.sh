#!/bin/bash

# Office Generator PPTX Conversion Test Script
# Usage: ./test-pptx-convert.sh [json-file]

set -e

OFFICE_GENERATOR_URL="${OFFICE_GENERATOR_URL:-http://localhost:3001}"
JSON_FILE="${1:-test-samples/simple-test.json}"
OUTPUT_DIR="test-output"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Office Generator PPTX Conversion Test ===${NC}"
echo ""

# Check if Office Generator is running
echo -e "${BLUE}[1/5] Checking Office Generator health...${NC}"
if curl -s "${OFFICE_GENERATOR_URL}/api/pptx/health" > /dev/null; then
    echo -e "${GREEN}✓ Office Generator is running${NC}"
else
    echo -e "${RED}✗ Office Generator is not running at ${OFFICE_GENERATOR_URL}${NC}"
    echo "Please start it with: cd office-generator-service && npm start"
    exit 1
fi

# Check if JSON file exists
echo -e "${BLUE}[2/5] Checking JSON file...${NC}"
if [ ! -f "$JSON_FILE" ]; then
    echo -e "${RED}✗ JSON file not found: $JSON_FILE${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Found: $JSON_FILE${NC}"

# Create output directory
echo -e "${BLUE}[3/5] Creating output directory...${NC}"
mkdir -p "$OUTPUT_DIR"
echo -e "${GREEN}✓ Output directory: $OUTPUT_DIR${NC}"

# Read JSON and prepare request
echo -e "${BLUE}[4/5] Preparing request...${NC}"
JSON_CONTENT=$(cat "$JSON_FILE")
TITLE=$(echo "$JSON_CONTENT" | grep -o '"title"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/"title"[[:space:]]*:[[:space:]]*"\([^"]*\)"/\1/')
SLIDE_COUNT=$(echo "$JSON_CONTENT" | grep -o '"slides"' | wc -l)
echo -e "  Title: ${TITLE}"
echo -e "  Slides: ${SLIDE_COUNT}"

# Create request payload
REQUEST_PAYLOAD=$(cat <<EOF
{
  "outlineJson": $JSON_CONTENT,
  "options": {
    "theme": "business"
  }
}
EOF
)

# Send request
echo -e "${BLUE}[5/5] Sending conversion request...${NC}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="${OUTPUT_DIR}/test_${TIMESTAMP}.pptx"

HTTP_CODE=$(curl -s -w "%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -d "$REQUEST_PAYLOAD" \
    "${OFFICE_GENERATOR_URL}/api/pptx/convert" \
    -o "$OUTPUT_FILE")

if [ "$HTTP_CODE" = "200" ]; then
    FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo -e "${GREEN}✓ PPTX generated successfully!${NC}"
    echo -e "  Output: $OUTPUT_FILE"
    echo -e "  Size: $FILE_SIZE"
    echo ""
    echo -e "${GREEN}=== Test Completed Successfully ===${NC}"
    echo -e "Open the file: ${BLUE}$OUTPUT_FILE${NC}"
else
    echo -e "${RED}✗ Conversion failed with HTTP $HTTP_CODE${NC}"
    if [ -f "$OUTPUT_FILE" ]; then
        echo "Error response:"
        cat "$OUTPUT_FILE"
        rm "$OUTPUT_FILE"
    fi
    exit 1
fi
