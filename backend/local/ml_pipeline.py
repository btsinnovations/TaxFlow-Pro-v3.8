"""Local model training pipeline for transaction categorization.

Trains a TF-IDF + LogisticRegression classifier on the user's own labeled
transactions. No cloud ML APIs are used. Models are saved to disk as local
artifacts owned by the user.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .settings import LOCAL_ROOT


class TrainingError(Exception):
    pass


@dataclass
class TrainingResult:
    accuracy: float
    f1_macro: float
    support: int
    classes: List[str]
    model_path: Path
    vectorizer_path: Path
    report: Dict[str, Any]


def _load_training_data(
    transactions: List[Dict[str, Any]],
    min_samples_per_class: int = 2,
) -> tuple[List[str], List[str]]:
    """Validate and return (descriptions, labels) from raw transaction dicts."""
    descriptions: List[str] = []
    labels: List[str] = []
    for tx in transactions:
        desc = str(tx.get("description", "")).strip()
        cat = str(tx.get("category", "")).strip()
        if desc and cat and cat.lower() != "uncategorized":
            descriptions.append(desc)
            labels.append(cat)

    if len(descriptions) < 10:
        raise TrainingError("Need at least 10 labeled transactions to train.")

    from collections import Counter
    counts = Counter(labels)
    for cls, count in counts.items():
        if count < min_samples_per_class:
            raise TrainingError(
                f"Class '{cls}' has only {count} samples (min {min_samples_per_class})."
            )

    return descriptions, labels


def _build_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    stop_words="english",
                    ngram_range=(1, 2),
                    min_df=1,
                    max_features=5000,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    solver="lbfgs",
                ),
            ),
        ]
    )


def train_local_model(
    transactions: List[Dict[str, Any]],
    model_dir: Optional[Path] = None,
    test_size: float = 0.2,
    random_state: int = 42,
) -> TrainingResult:
    """Train a local TF-IDF + LogisticRegression model on user transactions."""
    descriptions, labels = _load_training_data(transactions)

    X_train, X_test, y_train, y_test = train_test_split(
        descriptions,
        labels,
        test_size=test_size,
        random_state=random_state,
    )

    pipeline = _build_pipeline()
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    report = classification_report(
        y_test,
        y_pred,
        output_dict=True,
        zero_division=0,
    )

    accuracy = float(report["accuracy"])
    f1_macro = float(report["macro avg"]["f1-score"])

    model_dir = model_dir or (LOCAL_ROOT / "ml")
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / "local_model.pkl"
    vectorizer_path = model_dir / "local_vectorizer.pkl"

    joblib.dump(pipeline, model_path)
    joblib.dump(pipeline.named_steps["tfidf"], vectorizer_path)

    meta = {
        "accuracy": accuracy,
        "f1_macro": f1_macro,
        "support": len(labels),
        "classes": sorted(set(labels)),
        "model_path": str(model_path),
    }
    (model_dir / "model_meta.json").write_text(json.dumps(meta, indent=2))

    return TrainingResult(
        accuracy=accuracy,
        f1_macro=f1_macro,
        support=len(labels),
        classes=sorted(set(labels)),
        model_path=model_path,
        vectorizer_path=vectorizer_path,
        report=report,
    )


def load_local_model(model_dir: Optional[Path] = None) -> Optional[Pipeline]:
    """Load a previously trained local model, if it exists."""
    model_dir = model_dir or (LOCAL_ROOT / "ml")
    model_path = model_dir / "local_model.pkl"
    if not model_path.exists():
        return None
    return joblib.load(model_path)


def predict_local(
    description: str,
    model: Optional[Pipeline] = None,
) -> tuple[str, float]:
    """Predict category for a single description using the local model."""
    if model is None:
        model = load_local_model()
    if model is None:
        raise TrainingError("No local model found. Train one first.")

    proba = model.predict_proba([description])[0]
    idx = int(np.argmax(proba))
    category = model.classes_[idx]
    confidence = float(proba[idx])
    return category, confidence
