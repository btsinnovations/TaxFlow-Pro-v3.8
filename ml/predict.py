# predict.py
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import joblib
import sklearn

from text_utils import clean_text

# -----------------------------
# Rule fallback – replace with your actual YAML engine
# -----------------------------
try:
    from rule_engine import rule_based_categorize
except ImportError:
    def rule_based_categorize(description: str, payee: str = "") -> str:
        print("WARNING: rule_based_categorize not implemented – returning 'Uncategorized'.",
              file=sys.stderr)
        return "Uncategorized"

# -----------------------------
# Paths
# -----------------------------
SCRIPT_DIR = Path(__file__).parent
MODEL_PATH = SCRIPT_DIR / "category_model.pkl"
META_PATH = SCRIPT_DIR / "model_metadata.json"
REVIEW_FILE = SCRIPT_DIR / "low_confidence_review.csv"

# -----------------------------
# Low‑confidence review logging
# -----------------------------
def _log_low_confidence(payee, description, confidence, predicted):
    file_exists = REVIEW_FILE.exists()
    with open(REVIEW_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "payee", "description",
                             "confidence", "predicted_category"])
        writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            payee,
            description,
            round(confidence, 4),
            predicted
        ])

# -----------------------------
# Model loader (with version check)
# -----------------------------
_MODEL = None
_THRESHOLD = 0.6

def _load_model():
    global _MODEL, _THRESHOLD

    if _MODEL is not None:
        return _MODEL

    if not MODEL_PATH.exists():
        raise FileNotFoundError("Model file not found. Run train_categorizer.py first.")

    _MODEL = joblib.load(MODEL_PATH)

    if META_PATH.exists():
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        _THRESHOLD = meta.get("confidence_threshold", 0.6)

        trained_ver = meta.get("sklearn_version")
        current_ver = sklearn.__version__
        if trained_ver and trained_ver != current_ver:
            print(
                f"\nWarning: model was trained with scikit‑learn {trained_ver}, "
                f"running {current_ver}.\n",
                file=sys.stderr
            )

    return _MODEL

# -----------------------------
# Public API – always returns a category
# -----------------------------
def categorize(description: str, payee: str = "") -> Dict:
    """
    Return category decision with metadata.

    Returns
    -------
    dict with keys:
        category   : str          assigned category
        method     : "model" | "rule"
        confidence : float        model confidence (0‑1), 0.0 if model absent
    """
    cleaned = clean_text(f"{payee} {description}")

    # Graceful fallback if model unavailable
    try:
        model = _load_model()
    except FileNotFoundError:
        return {
            "category": rule_based_categorize(description, payee),
            "method": "rule",
            "confidence": 0.0
        }

    probas = model.predict_proba([cleaned])[0]
    idx = probas.argmax()
    confidence = float(probas[idx])
    predicted_cat = model.classes_[idx]

    if confidence >= _THRESHOLD:
        return {
            "category": predicted_cat,
            "method": "model",
            "confidence": confidence
        }

    # Low confidence → fallback to rules + review queue
    _log_low_confidence(payee, description, confidence, predicted_cat)

    fallback = rule_based_categorize(description, payee)
    return {
        "category": fallback,
        "method": "rule",
        "confidence": confidence
    }
