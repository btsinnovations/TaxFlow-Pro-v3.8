#!/bin/bash
# scripts/batch_process.sh -- TaxFlow Pro v3.8 Backend Compliant
# Handles both PDF (multipart upload) and CSV/Excel (server-local path) files.

set -e

API_URL="${API_URL:-http://localhost:8000}"
INPUT_DIR="${INPUT_DIR:-./input}"
CLIENT_ID="${CLIENT_ID:-batch}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-csv}"

echo "=========================================="
echo "  TaxFlow Pro Batch Processor v3.8"
echo "=========================================="
echo "API:       $API_URL"
echo "Input:     $INPUT_DIR"
echo "Client ID: $CLIENT_ID"
echo "Output:    $OUTPUT_FORMAT"
echo ""

if [ ! -d "$INPUT_DIR" ]; then
    echo "[ERROR] Input directory $INPUT_DIR not found."
    exit 1
fi

processed=0
failed=0

for file in "$INPUT_DIR"/*; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        echo "Processing $filename..."

        if [[ "$filename" == *.pdf ]]; then
            # PDFs route to the generic parser (accepts multipart file upload)
            HTTP_STATUS=$(curl -s -o /tmp/resp.txt -w "%{http_code}" \
                -X POST "$API_URL/api/upload/parse-pdf" \
                -F "file=@$file" \
                -F "client_id=$CLIENT_ID" \
                -F "output_format=$OUTPUT_FORMAT")
        else
            # CSV/Excel route to the local pipeline (expects server filesystem path)
            abs_path=$(realpath "$file")
            HTTP_STATUS=$(curl -s -o /tmp/resp.txt -w "%{http_code}" \
                -X POST "$API_URL/api/upload/process-local" \
                -F "file_path=$abs_path" \
                -F "client_id=$CLIENT_ID" \
                -F "output_format=$OUTPUT_FORMAT")
        fi

        if [ "$HTTP_STATUS" -eq 200 ]; then
            echo "  Success (HTTP 200) for $filename"
            ((processed++))
        else
            echo "  Failed (HTTP $HTTP_STATUS) for $filename"
            cat /tmp/resp.txt
            echo ""
            ((failed++))
        fi
    fi
done

echo ""
echo "=========================================="
echo "  Batch complete: $processed OK, $failed FAILED"
echo "=========================================="
