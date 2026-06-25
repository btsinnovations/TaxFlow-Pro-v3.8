# TASK-3.10.S17 — OCR Pipeline Sandboxing

**Owner:** TBD  
**Goal:** Isolate PDF→image→OCR subprocesses with restricted network and filesystem access.

## Files

- `backend/parsers/generic_pdf.py`
- `backend/local/guards.py`
- `backend/parsers/sandbox.py`
- `backend/tests/test_ocr_sandbox.py`

## Requirements

1. Run Poppler/pdf2image and Tesseract in a subprocess.
2. Subprocess has no network access and only read/write to a temp directory.
3. Timeouts prevent runaway OCR.
4. Validate output before returning to main process.

## Tests

- OCR sandbox completes normal PDF.
- Network access blocked in sandbox (where testable on host).
- Timeout kills hanging subprocess.

## Report

Files changed, sandbox design, test results.
