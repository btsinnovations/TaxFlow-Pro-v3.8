# TASK-3.10.T02 — LightGBM Classifier

**Owner:** TBD  
**Goal:** Evaluate and optionally replace scikit-learn classifier with LightGBM for transaction categorization.

## Files

- `backend/services/lightgbm_categorizer.py`
- `phase3_pipeline/ml_categorizer.py`
- `phase3_pipeline/train_categorizer.py`
- `backend/tests/test_lightgbm_classifier.py`

## Requirements

1. Train offline on existing categorized data.
2. Compare accuracy, model size, and training time vs. current scikit-learn approach.
3. Handle imbalanced categories.
4. Fallback to current classifier if LightGBM fails or is not installed.

## Tests

- Training script runs and produces a model.
- Inference matches or beats current accuracy on a held-out test set.
- Model size is smaller or justified.

## Report

Decision: adopt, keep parallel, or reject. Include metrics.
