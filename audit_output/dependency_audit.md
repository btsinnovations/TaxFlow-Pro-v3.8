# Dependency Audit Report (TASK-038.8)
Generated: 2026-06-23  Python: 3.14.2  Total packages reviewed: 35  Project imports parsed: 252  Safe: 30 | Needs review: 4 | Network opt-in: 1 | Unused: 0
## Packages Flagged for Review
| Package | Version | Reason | Match Count |
|---|---|---|---|
| opencv-python-headless | 4.13.0.92 | Source samples contain network/telemetry/update-check patterns | 14 |
| pytest | 9.1.0 | Source samples contain network/telemetry/update-check patterns | 14 |
| pywin32 | 311 | Source samples contain network/telemetry/update-check patterns | 14 |
| reportlab | 4.4.10 | Source samples contain network/telemetry/update-check patterns | 14 |

## Network-Capable Packages (verify no ungated use)
| Package | Version | Reason | Action |
|---|---|---|---|
| requests | 2.32.5 | HTTP client. Verify no import in backend runtime source. | Confirm no project import or gate usage |

## All Reviewed Packages
| Package | Version | Category | Reason | Imported | In requirements |
|---|---|---|---|---|---|
| PyPDF2 | 3.0.1 | safe | PDF text extraction (local) | Yes | Yes |
| PyYAML | 6.0.3 | safe | YAML parser (local) | Yes | No |
| SQLAlchemy | 2.0.50 | safe | ORM (local DB bindings) | Yes | No |
| alembic | 1.18.4 | safe | Migration tool (local DB) | Yes | Yes |
| bcrypt | 5.0.0 | safe | Password hashing (local) | Yes | Yes |
| cryptography | 48.0.0 | safe | Crypto primitives (local) | Yes | Yes |
| fastapi | 0.136.3 | safe | Web framework (local server only) | Yes | Yes |
| fpdf2 | 2.8.7 | safe | PDF generation (local) | Yes | Yes |
| joblib | 1.5.3 | safe | ML serialization (local) | Yes | Yes |
| keyring | 25.7.0 | safe | Credential store (local OS API) | Yes | Yes |
| numpy | 2.4.2 | safe | Numeric computing (local) | Yes | No |
| opencv-python-headless | 4.13.0.92 | needs-review | Source samples contain network/telemetry/update-check patterns | Yes | No |
| openpyxl | 3.1.5 | safe | Excel read/write (local) | Yes | Yes |
| pandas | 3.0.1 | safe | Data frames (local) | Yes | Yes |
| pdf2image | 1.17.0 | safe | PDF→image wrapper (local, calls local poppler) | Yes | Yes |
| pdfplumber | 0.11.9 | safe | PDF text extraction (local) | Yes | Yes |
| pillow | 12.1.1 | safe | Image processing (local) | Yes | Yes |
| psycopg2-binary | 2.9.12 | safe | PostgreSQL driver (connects only to configured DB) | No | Yes |
| pyarrow | 24.0.0 | safe | Columnar data (local) | No | Yes |
| pydantic | 2.13.4 | safe | Validation (local) | Yes | No |
| pytesseract | 0.3.13 | safe | OCR wrapper (local, calls local Tesseract) | Yes | Yes |
| pytest | 9.1.0 | needs-review | Source samples contain network/telemetry/update-check patterns | Yes | No |
| python-dateutil | 2.9.0.post0 | safe | Date parsing (local) | Yes | No |
| python-dotenv | 1.2.2 | safe | Env loader (local file) | Yes | Yes |
| python-jose | 3.5.0 | safe | JWT handling (local) | Yes | Yes |
| python-multipart | 0.0.32 | safe | Form parser (local) | No | Yes |
| pywin32 | 311 | needs-review | Source samples contain network/telemetry/update-check patterns | Yes | No |
| pyyaml | 6.0.3 | safe | YAML parser (local) | No | Yes |
| reportlab | 4.4.10 | needs-review | Source samples contain network/telemetry/update-check patterns | Yes | No |
| requests | 2.32.5 | network-opt-in | HTTP client. Verify no import in backend runtime source. | No | Yes |
| scikit-learn | 1.9.0 | safe | ML (local) | Yes | Yes |
| sqlalchemy | 2.0.50 | safe | ORM (local DB bindings) | No | Yes |
| sqlcipher3 | 0.6.2 | safe | SQLCipher binding (local encryption) | Yes | No |
| starlette | 1.3.1 | safe | ASGI toolkit (local) | Yes | No |
| uvicorn | 0.49.0 | safe | ASGI server (local) | Yes | Yes |
