import pytest
from pathlib import Path
from phase3_pipeline.ml_categorizer import MLCategorizer

def test_ml_missing_model(monkeypatch):
    # Simulate missing model file
    monkeypatch.setattr(Path, "exists", lambda self: False)
    ml = MLCategorizer()
    assert ml.enabled is False