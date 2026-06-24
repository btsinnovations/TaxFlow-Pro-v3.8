#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PID_FILE="$PROJECT_DIR/.backend.pid"

echo "→ Stopping TaxFlow Pro..."

if [ -f "$BACKEND_PID_FILE" ]; then
    kill -9 $(cat "$BACKEND_PID_FILE") 2>/dev/null || true
    rm -f "$BACKEND_PID_FILE"
fi

pkill -f "vite" 2>/dev/null || true
pkill -f "node.*Financial ETL" 2>/dev/null || true

echo "✓ All services stopped."
