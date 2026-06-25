# TASK-3.10.T03 — ONNX Runtime Inference

**Owner:** TBD  
**Goal:** Remove `joblib` pickle deserialization risk by exporting the categorizer to ONNX and running inference via ONNX Runtime.

## Files

- `backend/services/onnx_categorizer.py`
- `phase3_pipeline/ml_categorizer.py`
- `scripts/export_model_to_onnx.py`
- `backend/tests/test_onnx_inference.py`

## Requirements

1. Export current scikit-learn model to ONNX via `skl2onnx`.
2. Run inference with `onnxruntime`.
3. Preserve prediction behavior and confidence thresholds.
4. Keep fallback to current `joblib` model if ONNX file missing.

## Tests

- ONNX export script produces a valid `.onnx` file.
- ONNX inference returns same labels as current model for sample transactions.
- Missing ONNX file falls back gracefully.

## Report

Files changed, inference latency comparison, migration path for existing `joblib` models.
