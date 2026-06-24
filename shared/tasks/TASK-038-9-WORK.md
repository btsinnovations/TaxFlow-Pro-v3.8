# TASK-038.9 Local ML Retrain Pipeline — Work Assignment

**Owner:** Jane  
**Approver:** btsinnovations (delegated by Josh)  
**Goal:** Complete the local ML retrain pipeline: user-labeled transactions → local TF-IDF+LR model artifact with integrity hash/manifest, no external ML APIs.

---

## Current state (pre-work done by orchestrator)

Read and analyzed the following files:

- `phase3_pipeline/ml_categorizer.py` — legacy `MLCategorizer` that loads `ml_model.pkl` produced by joblib; expects keys `pipeline`, `classes`, `threshold`.
- `phase3_pipeline/config.py` — sets `ML_MODEL_PATH = "ml_model.pkl"`, `USE_ML = True`, `ML_CONFIDENCE_THRESHOLD = 0.7`.
- `backend/local/ml_pipeline.py` — newer local training pipeline: `train_local_model`, `load_local_model`, `predict_local`. Saves `local_model.pkl`, `local_vectorizer.pkl`, `model_meta.json` under `LOCAL_ROOT / "ml"`.
- `backend/routers/ml.py` — `/ml/status`, `/ml/train`, `/ml/model-info`, `/ml/categorize/{statement_id}` using the newer pipeline.
- `backend/local/bootstrap.py` — checks for `ml/model.joblib` + `ml/model_meta.json`; currently expects `.joblib` extension but pipeline writes `.pkl`.
- `backend/models.py` — no model-registry table yet.
- `backend/tests/test_local_first.py` — crypto/offline tests only; no ML pipeline tests.

**Gap identified:** The newer pipeline in `backend/local/ml_pipeline.py` works, but it does not:
1. Compute/store a SHA-256 integrity hash for the model artifact.
2. Warn or reject when loading a model whose manifest/hash is missing or mismatched (imported model safety, requirement 3.4d).
3. Persist model training history/versioning in the database.
4. Align with `backend/local/bootstrap.py` which looks for `model.joblib` instead of `local_model.pkl`.

Also, two parallel categorizer implementations exist (`phase3_pipeline/ml_categorizer.py` vs `backend/local/ml_pipeline.py`). For TASK-038.9 we focus on completing and hardening the newer `backend/local/ml_pipeline.py` path; unification can be a follow-up.

---

## Jane's tasks

### 1. Add integrity hashing to model artifacts

Update `backend/local/ml_pipeline.py`:

- After writing `local_model.pkl`, compute its SHA-256 hash.
- Store the hash in `model_meta.json` under key `model_sha256`.
- Also store `vectorizer_sha256` if a separate vectorizer file is written.
- Use a deterministic manifest schema:

```json
{
  "accuracy": 0.92,
  "f1_macro": 0.91,
  "support": 150,
  "classes": ["Food & Dining", "Income", ...],
  "model_path": "/path/to/ml/local_model.pkl",
  "model_sha256": "abc123...",
  "vectorizer_sha256": "def456...",
  "trained_at": "2026-06-23T10:30:00Z",
  "version": 1
}
```

### 2. Add safe model loading helper

Add a new function in `backend/local/ml_pipeline.py`:

```python
def load_local_model_safe(model_dir: Optional[Path] = None) -> Optional[Pipeline]:
    """Load a local model only if its SHA-256 manifest is valid.

    Raises TrainingError if the model file is missing or the manifest/hash
    does not match. This prevents `joblib.load()` from executing a tampered
    or imported model artifact without warning.
    """
```

Behavior:
- If `local_model.pkl` does not exist → return `None`.
- If `model_meta.json` does not exist → log a warning and return `None` (do not load an unmanifested artifact).
- If `model_sha256` in manifest does not match the file hash → raise `TrainingError("Model integrity check failed")`.
- If all checks pass → return `joblib.load(local_model.pkl)`.

Update `load_local_model` to delegate to `load_local_model_safe` so the existing router path benefits.

### 3. Fix bootstrap artifact detection

Update `backend/local/bootstrap.py` `_model_artifacts_available()`:

- Check for `ml/local_model.pkl` and `ml/model_meta.json` (matching the pipeline output).
- Keep the current function signature and return behavior.

### 4. Add model registry table (optional but recommended)

Add to `backend/models.py`:

```python
class TrainedModel(Base):
    __tablename__ = "trained_models"
    __table_args__ = (Index("ix_trained_models_user_id", "user_id"),)
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    model_path = Column(String, nullable=False)
    model_sha256 = Column(String(64), nullable=False)
    accuracy = Column(Numeric(5, 4), nullable=True)
    f1_macro = Column(Numeric(5, 4), nullable=True)
    support = Column(Integer, nullable=True)
    classes = Column(String, nullable=True)  # comma-separated or JSON
    trained_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    is_active = Column(Boolean, default=True)

    owner = relationship("User", back_populates="trained_models")
```

Add `trained_models = relationship("TrainedModel", back_populates="owner")` to `User`.

Update `backend/routers/ml.py` `/ml/train` to insert a `TrainedModel` row after training succeeds, marking prior rows `is_active=False` for the user.

Create Alembic migration for the new table.

### 5. Extend `/ml/train` response

Return the model integrity hash and registry version:

```json
{
  "accuracy": 0.92,
  "f1_macro": 0.91,
  "support": 150,
  "classes": [...],
  "model_path": "...",
  "model_sha256": "...",
  "version": 1
}
```

### 6. Add tests

Create `backend/tests/test_ml_pipeline.py` (or extend `test_local_first.py`):

- `test_train_local_model_creates_manifest_with_hash`
  - Train on synthetic labeled data.
  - Assert `model_meta.json` exists and contains `model_sha256`.
  - Assert the hash matches the actual file hash.

- `test_load_local_model_safe_succeeds_with_valid_manifest`
  - Train, load, predict.
  - Assert category returned.

- `test_load_local_model_safe_rejects_tampered_model`
  - Train, corrupt `local_model.pkl` bytes, assert `TrainingError` on load.

- `test_load_local_model_safe_rejects_missing_manifest`
  - Train, delete `model_meta.json`, assert `None` or `TrainingError` (match your chosen behavior).

- `test_ml_train_endpoint_requires_authentication`
  - POST `/api/ml/train` without token → 401.

- `test_ml_train_endpoint_insufficient_labels`
  - POST `/api/ml/train` with <10 labeled transactions → 400.

- `test_ml_train_endpoint_succeeds`
  - Boot, seed 10+ labeled transactions, POST `/api/ml/train`, assert 200 + `model_sha256` present.

### 7. Update `docs/TODO_FIRST.md`

Mark Phase 3 Gap **3.6 Local model training pipeline** as ✅ complete.

### 8. Update `CHANGES.md`

Add a new section (Section 36 if Section 35 is local auth) documenting:
- Files changed: `backend/local/ml_pipeline.py`, `backend/routers/ml.py`, `backend/local/bootstrap.py`, `backend/models.py`.
- Files added: `backend/tests/test_ml_pipeline.py`, Alembic migration.
- Behavior: integrity hashing, safe loading, model registry, no external ML APIs.
- Verification commands and expected pass counts.

### 9. Run tests and report

```bash
python -m pytest backend/tests/test_ml_pipeline.py -q
python -m pytest backend/tests/test_bootstrap.py -q
python -m pytest backend/tests -q
python -m pytest tests -q
```

Report pass/fail counts.

---

## Implementation notes

### Hash helper

```python
import hashlib

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
```

### Training data helper for tests

```python
TRAINING_SEED = [
    {"description": "STARBUCKS #123 MIAMI", "category": "Food & Dining"},
    {"description": "SHELL OIL 456", "category": "Auto & Transport"},
    {"description": "PAYROLL DEPOSIT", "category": "Income"},
    # ... at least 10 entries, 2+ per class
]
```

### No external ML APIs

The pipeline must continue to use only scikit-learn. Do not add Hugging Face, OpenAI, or any cloud provider.

---

## Constraints

- Do not change `phase3_pipeline/ml_categorizer.py` unless necessary; focus on `backend/local/ml_pipeline.py`.
- Do not remove the existing `/ml/train` endpoint; extend it.
- Do not restart gateway or modify OpenClaw config.
- Keep all changes local-first / no network.
- Escalate blockers via `sessions_send` to James.

---

## Expected output

- Updated `backend/local/ml_pipeline.py` with integrity hashing + safe loader.
- Updated `backend/routers/ml.py` with registry persistence + extended response.
- Updated `backend/local/bootstrap.py` artifact detection.
- Updated `backend/models.py` with `TrainedModel` table (if doing registry).
- Alembic migration for the new table.
- New `backend/tests/test_ml_pipeline.py`.
- Updated `docs/TODO_FIRST.md` and `CHANGES.md`.
- Test report with 0 failures.

Start when ready. Report progress via sessions_send only.
