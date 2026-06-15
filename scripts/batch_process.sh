#!/bin/bash
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
