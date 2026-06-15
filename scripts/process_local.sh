#!/bin/bash
# process_local.sh — CLI wrapper for API local-file processing

API_URL="http://localhost:8000"
DEFAULT_ORIGIN="$HOME/Documents/BankStatements"
DEFAULT_DEST="$HOME/Documents/ExtractedData"

echo "=== TaxFlow Pro — Local File Processing ==="
echo ""

# Prompt for origin
read -p "Source folder [$DEFAULT_ORIGIN]: " ORIGIN
ORIGIN=${ORIGIN:-$DEFAULT_ORIGIN}

# Prompt for destination
read -p "Destination folder [$DEFAULT_DEST]: " DEST
DEST=${DEST:-$DEFAULT_DEST}

# Ensure folders exist
mkdir -p "$ORIGIN" "$DEST"

# List files
echo ""
echo "Files in $ORIGIN:"
ls -1 "$ORIGIN"/*.pdf "$ORIGIN"/*.csv 2>/dev/null || echo "  (none found)"

echo ""
read -p "Filename to process: " FILENAME
FILEPATH="$ORIGIN/$FILENAME"

if [ ! -f "$FILEPATH" ]; then
    echo "ERROR: File not found: $FILEPATH"
    exit 1
fi

echo ""
echo "Processing $FILENAME..."
echo "  Origin:  $FILEPATH"
echo "  Output:  $DEST"

curl -X POST "$API_URL/api/upload/process-local" \
  -F "file_path=$FILEPATH" \
  -F "output_folder=$DEST" \
  -F "client_id=1" \
  -F "output_format=qif" | python3 -m json.tool

echo ""
echo "Done. Check $DEST for results."
