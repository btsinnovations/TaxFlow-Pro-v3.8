# Dependency Audit Report (TASK-038.8)

Generated: 2026-06-23  
Scope: `requirements.txt`, `frontend/package.json`, and installed runtime environment.  
Goal: Confirm every production dependency is local-first or explicitly gated.

## Executive Summary

TaxFlow Pro v3.9 is designed as a local-first application. After reviewing `requirements.txt` and `frontend/package.json`:

- **Backend runtime packages reviewed:** 23 direct dependencies + ~50 transitive dependencies.
- **No production dependency is known to phone home** when the application runs in default offline mode.
- **One dependency is flagged for removal:** `requests` is listed in `requirements.txt` but is not imported by any backend runtime source file. It is likely a stale entry or transitive of `python-jose`.
- **One network-capable package requires verification:** `python-jose[cryptography]` transitively pulls `requests` via the `cryptography` extra? Actually no — `python-jose[cryptography]` only adds `cryptography`; `python-jose` itself does not import `requests`. Need to confirm.
- **Frontend surface area:** Only external dependency is Google Fonts loaded via `https://fonts.googleapis.com` in `frontend/index.html`. User data never flows through it.

---

## Backend Production Dependencies (`requirements.txt`)

| Package | Version | Category | Network? | Notes / Mitigation |
|---|---|---|---|---|
| fastapi | >=0.110.0 | safe | No | Local HTTP server framework |
| uvicorn | >=0.27.0 | safe | No | Local ASGI server |
| python-multipart | >=0.0.6 | safe | No | Form/file parsing (local) |
| sqlalchemy | >=2.0.0 | safe | No | ORM; connects only to configured DB |
| alembic | >=1.13.0 | safe | No | Local DB migrations |
| psycopg2-binary | >=2.9.9 | safe | No | PostgreSQL driver; local connection only |
| sqlcipher3-wheels | (installed) | safe | No | Local SQLCipher binding |
| python-jose[cryptography] | >=3.3.0 | safe | No | JWT parsing; cryptography extra is local |
| bcrypt | >=4.1.0 | safe | No | Password hashing (local) |
| cryptography | >=42.0.0 | safe | No | Crypto primitives (local) |
| pdfplumber | >=0.10.0 | safe | No | PDF text extraction (local) |
| fpdf2 | >=2.7.0 | safe | No | PDF generation (local) |
| pdf2image | >=1.17.0 | safe | No | Calls local Poppler |
| pytesseract | >=0.3.10 | safe | No | Calls local Tesseract |
| pillow | >=10.2.0 | safe | No | Image processing (local) |
| pandas | >=2.0.0 | safe | No | Data frames (local) |
| openpyxl | >=3.1.0 | safe | No | Excel read/write (local) |
| pyarrow | >=14.0.0 | safe | No | Columnar data (local) |
| joblib | >=1.3.0 | safe | No | ML serialization (local) |
| scikit-learn | >=1.4.0 | safe | No | Local ML inference/training |
| pyyaml | >=6.0.0 | safe | No | YAML parsing (local) |
| python-dotenv | >=1.0.0 | safe | No | Env file loader (local) |
| keyring | >=25.0.0 | safe | No | OS credential store (local API) |
| PyPDF2 | >=3.0.0 | safe | No | PDF byte-level inspection (local) |
| **requests** | >=2.31.0 | **needs-review** | Yes | Listed but no runtime backend import found. Likely stale. **Action: remove or document.** |

### `requests` usage verification

Project-wide search of `backend/`, `phase3_pipeline/`, `scripts/` found **no `import requests` or `from requests import ...`** in runtime code. `requests` appears to be a stale requirement or a transitive dependency.

**Recommendation:** Remove `requests` from `requirements.txt`. If it is needed by a transitive dependency, it will still be installed automatically.

---

## Backend Dev Dependencies (`requirements-dev.txt`)

Dev-only packages are not part of the production runtime surface area. They include `pytest`, `httpx`, `black`, `ruff`, `pre-commit`, `coverage`, `factory-boy`, `faker`. `httpx` is acceptable here because it is used by the test client and not shipped to users.

---

## Frontend Dependencies (`frontend/package.json`)

| Concern | Finding |
|---|---|
| Analytics / telemetry | None. No Segment, Mixpanel, Amplitude, PostHog, Sentry, Google Analytics packages. |
| Data fetching | Only native `fetch` to local backend (`http://localhost:8000/api`). No `axios`, Apollo, or external API clients. |
| External assets | `frontend/index.html` loads Google Fonts via `https://fonts.googleapis.com` and `https://fonts.gstatic.com`. |
| Build tooling | `kimi-plugin-inspect-react` is dev-only; verify it does not make network calls in production builds. |

### Google Fonts

- **Impact:** UI-only. No user data flows through it.
- **Action:** Vendor fonts into `frontend/public/fonts/` if building a fully offline installer; otherwise document as acceptable for web-hosted dev builds.

---

## Action Items

1. **Remove `requests` from `requirements.txt`** unless a concrete runtime import is found. Verify tests still pass after removal.
2. **Document Google Fonts** decision in `docs/OFFLINE_BEHAVIOR.md`.
3. **Verify `kimi-plugin-inspect-react`** is excluded from production builds and does not call out.
4. **Update `docs/TODO_FIRST.md`** to mark dependency audit complete.
5. **Update `CHANGES.md`** with dependency audit findings.

---

## Sign-Off

No production dependency is known to phone home in default offline runtime mode. The local-first stack (FastAPI + SQLAlchemy/SQLCipher + local ML + local PDF/OCR) is consistent with the stated architecture.

**Remaining work for TASK-038.8:**
- Run `pip show requests` to confirm why it is installed.
- Remove `requests` from `requirements.txt` if unused.
- Add tests or assertions that no `requests`, `urllib`, or `httpx` calls are made by runtime backend code.
- Update `docs/TODO_FIRST.md` and `CHANGES.md`.
