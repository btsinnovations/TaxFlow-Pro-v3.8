#!/bin/bash
<<<<<<< HEAD
set -e

API_URL="${API_URL:-http://localhost:8000}"
USERNAME="${USERNAME:-testuser}"
PASSWORD="${PASSWORD:-testpass123}"
INPUT_DIR="${INPUT_DIR:-./input}"

mkdir -p "$INPUT_DIR"

echo "=========================================="
echo "  TaxFlow Pro Batch Processor"
echo "=========================================="
echo "API:    $API_URL"
echo "User:   $USERNAME"
echo "Input:  $INPUT_DIR"
echo ""

echo "→ Authenticating..."
LOGIN_RESP=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$USERNAME&password=$PASSWORD")
TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")

if [ -z "$TOKEN" ]; then
    echo "❌ Login failed"
    echo "$LOGIN_RESP"
    exit 1
fi
echo "✅ Authenticated"
echo ""

PROCESSED=0
FAILED=0

for file in "$INPUT_DIR"/*.pdf; do
    [ -e "$file" ] || continue
    filename=$(basename "$file")
    echo "→ Processing PDF: $filename"
    resp=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/upload/" \
      -H "Authorization: Bearer $TOKEN" -F "file=@$file")
    http_code=$(echo "$resp" | tail -n1)
    body=$(echo "$resp" | sed '$d')
    if [ "$http_code" = "200" ]; then
        echo "  ✅ Success (HTTP $http_code)"
        ((PROCESSED++))
    else
        echo "  ❌ Failed (HTTP $http_code)"
        echo "$body"
        ((FAILED++))
    fi
    echo ""
done

echo "=========================================="
echo "  Batch complete: $PROCESSED OK, $FAILED FAILED"
echo "=========================================="
=======
# scripts/batch_process.sh — TaxFlow Pro v3.7 Backend Compliant
# Fixes: non-PDF branch now sends file_path= (server-local path) instead of file upload.
#        Adds client_id and output_format for proper backend logging.

API_URL="${API_URL:-http://localhost:8000}"
INPUT_DIR="${INPUT_DIR:-./input}"
CLIENT_ID="${CLIENT_ID:-batch}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-csv}"

echo "Starting batch process against $API_URL..."
echo "  Input dir : $INPUT_DIR"
echo "  Client ID : $CLIENT_ID"
echo "  Output fmt: $OUTPUT_FORMAT"
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
            echo "  ✅ Success (HTTP 200) for $filename"
            ((processed++))
        else
            echo "  ❌ Failed (HTTP $HTTP_STATUS) for $filename"
            cat /tmp/resp.txt
            echo ""
            ((failed++))
        fi
    fi
done

echo ""
echo "Batch processing complete."
echo "  Processed: $processed"
echo "  Failed   : $failed"
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
