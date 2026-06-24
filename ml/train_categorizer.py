# train_categorizer.py
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import joblib

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedKFold, cross_val_score, cross_val_predict
from sklearn.metrics import classification_report, f1_score

from text_utils import clean_text

# -----------------------------
# Config
# -----------------------------
SCRIPT_DIR = Path(__file__).parent
CSV_FILE = SCRIPT_DIR / "categorized_history.csv"
MODEL_FILE = SCRIPT_DIR / "category_model.pkl"
METADATA_FILE = SCRIPT_DIR / "model_metadata.json"

MIN_TRAINING_WARNING = 50

# Use all available cores by default.
# Set to 1 if your environment restricts multiprocessing.
CV_JOBS = -1

# -----------------------------
# Load data
# -----------------------------
if not CSV_FILE.exists():
    print(f"Error: {CSV_FILE} not found.")
    sys.exit(1)

df = pd.read_csv(CSV_FILE)

required_cols = {"Payee", "Description", "Category"}
if not required_cols.issubset(df.columns):
    print(f"Error: missing columns {required_cols}")
    sys.exit(1)

df["cleaned_text"] = (
    df["Payee"].fillna("") + " " + df["Description"].fillna("")
).apply(clean_text)

df = df[df["cleaned_text"].str.strip() != ""]

if len(df) < MIN_TRAINING_WARNING:
    print(f"Warning: only {len(df)} samples")

# -----------------------------
# Adaptive CV setup
# -----------------------------
class_counts = df["Category"].value_counts()
min_samples_per_class = int(class_counts.min())

if min_samples_per_class < 2:
    print("Error: each class must have at least 2 samples")
    sys.exit(1)

n_splits = min(5, min_samples_per_class)

X = df["cleaned_text"]
y = df["Category"]

cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

# -----------------------------
# Model pipeline
# -----------------------------
pipeline = Pipeline([
    ("tfidf", TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=10000,
        sublinear_tf=True,
        stop_words="english",
        min_df=2
    )),
    ("clf", LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=42
    ))
])

# -----------------------------
# Cross-validation
# -----------------------------
scores = cross_val_score(
    pipeline, X, y, cv=cv, scoring="accuracy", n_jobs=CV_JOBS
)

cv_preds = cross_val_predict(
    pipeline, X, y, cv=cv,
    method="predict",
    n_jobs=CV_JOBS
)

probas_cv = cross_val_predict(
    pipeline, X, y, cv=cv,
    method="predict_proba",
    n_jobs=CV_JOBS
)

print(classification_report(y, cv_preds, zero_division=0))

# -----------------------------
# Deterministic confidence threshold grid
# -----------------------------
confidences = np.max(probas_cv, axis=1)
thresholds = np.arange(0.50, 0.96, 0.05)

best_thresh = 0.5
best_f1 = 0.0
best_coverage = 0.0

for thresh in thresholds:
    mask = confidences >= thresh
    if mask.sum() < 10:
        continue

    coverage = mask.mean()
    f1 = f1_score(y[mask], cv_preds[mask], average="macro", zero_division=0)

    # Prefer higher coverage when F1 is essentially tied
    if (f1 > best_f1) or (np.isclose(f1, best_f1) and coverage > best_coverage):
        best_f1 = f1
        best_thresh = float(thresh)
        best_coverage = float(coverage)

print(f"\nSuggested threshold: {best_thresh:.3f}  (coverage: {best_coverage:.1%}, macro F1: {best_f1:.3f})")

# -----------------------------
# Train final model & save
# -----------------------------
pipeline.fit(X, y)
joblib.dump(pipeline, MODEL_FILE)

metadata = {
    "features": "cleaned_text (payee + description)",
    "ngram_range": [1, 2],
    "max_features": 10000,
    "class_weight": "balanced",
    "cv_folds": n_splits,
    "rarest_category_count": min_samples_per_class,
    "cv_accuracy": float(scores.mean()),
    "confidence_threshold": round(float(best_thresh), 3),
    "threshold_coverage": round(float(best_coverage), 4),
    "threshold_macro_f1": round(float(best_f1), 4),
    "training_samples": len(df),
    "categories": list(pipeline.classes_),
    "sklearn_version": sklearn.__version__
}

with open(METADATA_FILE, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2)

print(f"Saved model → {MODEL_FILE}")
print(f"Saved metadata → {METADATA_FILE}")
print("\nRe-run after appending corrected transactions.")
