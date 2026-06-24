#!/bin/bash
INPUT_DIR="data/input"
OUTPUT_DIR="data/output"
ARCHIVE_DIR="data/archive"

mkdir -p "$INPUT_DIR" "$OUTPUT_DIR" "$ARCHIVE_DIR"

for file in "$INPUT_DIR"/*.csv; do
    [ -e "$file" ] || continue
    base=$(basename "$file")
    echo "Processing $base ..."
    python -m phase3_pipeline.main "$file" "$OUTPUT_DIR/transformed_${base%.csv}.csv"
    mv "$file" "$ARCHIVE_DIR/"
done

echo "All files processed."