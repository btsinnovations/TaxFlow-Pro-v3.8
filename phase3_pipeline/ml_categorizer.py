"""
<<<<<<< HEAD
Offline ML categorizer using TF‑IDF + Logistic Regression.
Loads a pre‑trained model and returns category + confidence.
=======
Offline ML categorizer using TF-IDF + Logistic Regression.
Loads a pre-trained model and returns category + confidence.
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
"""
import joblib
import numpy as np
from pathlib import Path
from .config import USE_ML, ML_CONFIDENCE_THRESHOLD, ML_MODEL_PATH
from .text_utils import clean_text
from .categorizer import PriorityCategorizer   # your existing priority categorizer

class MLCategorizer:
    def __init__(self):
        self.model = None
        self.classes = None
<<<<<<< HEAD
        self.priority_cat = PriorityCategorizer("categories.yaml")
        self.enabled = USE_ML
        self.threshold = ML_CONFIDENCE_THRESHOLD
        self._load_model()
    
=======
        self.priority_cat = None
        self.enabled = USE_ML
        self.threshold = ML_CONFIDENCE_THRESHOLD
        self._load_priority_cat()
        self._load_model()

    def _load_priority_cat(self):
        """Load the rule-based fallback categorizer. Tolerates a missing categories file."""
        # Resolve categories.yaml relative to the project root (phase3_pipeline parent)
        candidate = Path(__file__).parent.parent / "categories.yaml"
        if not candidate.exists():
            candidate = Path("categories.yaml")
        try:
            self.priority_cat = PriorityCategorizer(str(candidate))
        except FileNotFoundError as e:
            print(f"Warning: {e}. Rule-based fallback disabled.")
            self.priority_cat = None
            self.enabled = False

>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
    def _load_model(self):
        if not self.enabled:
            return
        model_file = Path(ML_MODEL_PATH)
        if model_file.exists():
            try:
                data = joblib.load(model_file)
                # Expect dict with keys: 'pipeline', 'classes', 'threshold'
                self.model = data['pipeline']
                self.classes = data['classes']
                # Use stored threshold if present, else config value
                self.threshold = data.get('threshold', self.threshold)
                print(f"ML model loaded from {model_file} (threshold={self.threshold})")
            except Exception as e:
                print(f"Warning: failed to load ML model: {e}")
                self.enabled = False
        else:
            print(f"ML model file {model_file} not found. ML disabled.")
            self.enabled = False
<<<<<<< HEAD
    
=======

>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
    def predict(self, description: str, payee: str = "") -> tuple:
        """
        Returns: (category, confidence, method)
        method is either 'ml', 'rule', or 'rule_fallback'
        """
        if not self.enabled or self.model is None:
<<<<<<< HEAD
            cat = self.priority_cat.categorize(description, payee)
            return cat, 1.0, 'rule'
        
=======
            cat = self.priority_cat.categorize(description, payee) if self.priority_cat else "Other:Uncategorized"
            return cat, 1.0, 'rule'

>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
        text = clean_text(f"{payee} {description}")
        # Get probability scores
        proba = self.model.predict_proba([text])[0]
        max_prob = np.max(proba)
        if max_prob >= self.threshold:
            idx = np.argmax(proba)
            category = self.classes[idx]
            return category, float(max_prob), 'ml'
        else:
<<<<<<< HEAD
            cat = self.priority_cat.categorize(description, payee)
=======
            cat = self.priority_cat.categorize(description, payee) if self.priority_cat else "Other:Uncategorized"
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
            return cat, float(max_prob), 'rule_fallback'