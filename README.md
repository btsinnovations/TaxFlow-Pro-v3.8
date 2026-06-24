# TaxFlow Pro v3.9.1

Local-first, offline-capable financial document processing for individuals and small businesses.

TaxFlow Pro ingests bank statements and financial documents, extracts transactions, categorizes them, and produces tax-ready exports — without ever sending your data to the cloud.

---

## What It Does

- **PDF statement parsing** — extracts transactions, balances, dates, and account metadata.
- **Tier 1 institution detection** — recognizes Navy Federal, U.S. Bank, Citibank, PNC, Ally, SoFi, Truist, Discover, Marcus by Goldman Sachs, and BECU.
- **Hash-chain audit trail** — tamper-evident logging for create/update/delete actions with end-to-end integrity verification via `GET /api/audit/verify`.
- **Fixed-asset depreciation** — local MACRS schedule computation with Section 179 and bonus depreciation.
- **Hybrid local auth** — bcrypt + JWT signed with `.local_secret`; first boot creates a single local admin.
- **Categorization rules engine** — auto-categorize transactions by description pattern with priority tie-breaking.
- **Tax-ready exports** — CSV (transactions, general ledger, trial balance, P&L, balance sheet), JSON, QIF, QBO, Xero, Excel, PDF summary, and Parquet.
- **Review flags** — flag transactions or GL entries for review and resolve them.
- **Workpaper references** — link transactions and GL entries to external workpaper identifiers.
- **Offline by default** — no Plaid, no live bank feeds, no telemetry, no internet required.

---

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
python -m alembic upgrade head
uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
```

By default the backend binds to **localhost only** (`127.0.0.1`). To expose it
on your LAN (e.g. for a mobile frontend on the same network), opt-in with the
`TAXFLOW_BIND_LAN=true` environment variable or pass `--host 0.0.0.0` explicitly.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Then open `http://localhost:5173`.

---

## Configuration

Copy `.env.example` to `.env` and set:

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | Database connection | `sqlite:///./taxflow.db` |
| `TAXFLOW_SECRET_KEY` | JWT signing secret override | `.local_secret` file |
| `TAXFLOW_LOCAL_SECRET_FILE` | Path to `.local_secret` | `.local_secret` |
| `TAXFLOW_MAX_UPLOAD_BYTES` | Maximum upload size in bytes | `33554432` (32 MiB) |
| `TAXFLOW_UPLOAD_MAGIC_STRICT` | Require PDF magic version 1.x/2.x | `false` |
| `ALEMBIC_CONFIG` | Path to `alembic.ini` | `alembic.ini` |
| `TAXFLOW_ENVIRONMENT` | Runtime environment (`development` \| `production`) | `development` |
| `TAXFLOW_CORS_ORIGINS` | Comma-separated CORS allow-list | local dev origins |
| `TAXFLOW_GLOBAL_RATE_LIMIT` | Per-IP sliding-window limit (e.g. `100/minute`) | `100/minute` |
| `TAXFLOW_GLOBAL_BURST_LIMIT` | Requests allowed before rate-limit enforcement | `10` |
| `TAXFLOW_TRUSTED_PROXY_HOPS` | Trusted proxy count for `X-Forwarded-For` | `0` |
| `TAXFLOW_BREACH_BLOOM_PATH` | Path to JSON bloom filter for breached passwords | built-in mini list |
| `TAXFLOW_AUDIT_PRIVATE_KEY_PATH` | Ed25519 private key PEM for signing audit entries | local-secret fallback |
| `TAXFLOW_MAX_BODY_SIZE_BYTES` | General request body limit (JSON/form, not uploads) | `10485760` (10 MiB) |

When `TAXFLOW_ENVIRONMENT=production`, the backend adds `Strict-Transport-Security` (HSTS) to every response.

## Rate Limiting

- **Global per-IP sliding window.** Every request counts against a per-client limit. Default: **100 requests/minute** with a **10-request burst**. Reconfigure with `TAXFLOW_GLOBAL_RATE_LIMIT` and `TAXFLOW_GLOBAL_BURST_LIMIT`.
- **Client IP detection.** By default the direct remote address is used. If the app runs behind trusted proxies, set `TAXFLOW_TRUSTED_PROXY_HOPS` to the number of proxies so the real client IP is extracted from `X-Forwarded-For`.
- **Auth brute-force protection.** Login endpoints keep the existing per-username progressive delay and 10-attempt lockout from `backend/auth_rate_limit.py`.

### Request size limits

- `TAXFLOW_MAX_BODY_SIZE_BYTES` caps JSON and non-upload bodies. Default: **10 MiB**.
- `TAXFLOW_MAX_UPLOAD_BYTES` still governs multipart PDF uploads. Default: **32 MiB** (unchanged).
- Requests exceeding the general body limit receive **413 Payload Too Large** with a `Retry-After` header.

---

## Authentication

v3.9.2 uses a hybrid local model backed by the OS credential store:

- **First boot:** call `POST /api/auth/boot` with a master password. The app stores the JWT signing secret in the OS credential store (`keyring`) and seeds the single local admin user. The response includes a short-lived access token and a long-lived refresh token.
- **Subsequent runs:** call `POST /api/auth/login` with the master password to receive a fresh access token + refresh token pair.
- **Token refresh:** call `POST /api/auth/refresh` with a valid refresh token to receive a rotated access + refresh pair. The old refresh token is invalidated after a successful rotation.
- **Theft detection:** reusing a rotated or revoked refresh token causes the entire refresh family to be revoked, preventing token replay.
- **Logout:** call `POST /api/auth/logout` with the current access token (and optional refresh token). Both tokens are revoked and the refresh family is invalidated.
- **Protected routes:** supply the access token in the `Authorization: Bearer <token>` header.
- The local admin username is derived from the hostname if simple, otherwise `local`.
- `/api/auth/register` is retained only for the v3.7 test suite; production deployments use `/api/auth/boot`.
- **Fallback:** if the OS credential store is unavailable (headless servers, containers, CI), the secret is read from and written to the `.local_secret` file at `TAXFLOW_LOCAL_SECRET_FILE`. An existing `.local_secret` is automatically migrated into the credential store on first boot.
- **Override:** set `TAXFLOW_SECRET_KEY` to bypass both the credential store and the file.

### Token lifetimes

| Token | Default lifetime | Environment variable |
|-------|------------------|----------------------|
| Access | 15 minutes | `TAXFLOW_TOKEN_EXPIRE_MINUTES` |
| Refresh | 30 days | `TAXFLOW_REFRESH_TOKEN_EXPIRE_DAYS` |

Refresh tokens are opaque 64-byte URL-safe secrets. Only SHA-256 hashes are persisted in the database; plaintext refresh tokens never leave the `boot`/`login`/`refresh` response bodies.

### Password policy

- Minimum **12 characters**.
- Minimum **~50 bits** of estimated entropy.
- Cannot contain the literal word `password` or the username.
- Cannot be in the local **common-password** list.
- Cannot be present in the **breach bloom filter** (`TAXFLOW_BREACH_BLOOM_PATH`).
- A small built-in list is used when no bloom filter is configured; production deployments should generate a real filter from a large breach corpus with `scripts/build_bloom_filter.py`.

### Audit integrity

- Each audit entry is linked into a **hash chain** (`chain_hash`) and signed with an **Ed25519 private key** (`TAXFLOW_AUDIT_PRIVATE_KEY_PATH`).
- `GET /api/audit/verify` recomputes the chain and verifies every signature.
- Any tampered row breaks both the chain and its signature.
- Production deployments should generate a dedicated Ed25519 key, keep the private key offline or in an HSM/kms, and publish only the public key for verification.

---

## Running Tests

```bash
python -m pytest backend/tests tests -v
```

Expected: **132 passed, 0 failed**

---

## Architecture

- **Backend:** FastAPI + SQLAlchemy + Alembic
- **Database:** SQLite default; optional local PostgreSQL
- **Frontend:** React + Vite
- **ML:** scikit-learn (TF-IDF + LogisticRegression) running locally
- **Auth:** bcrypt + local JWT signed with `.local_secret`
- **Packaging:** Browser + local server (Windows / macOS / Linux)

---

## v3.9 Stage 2 Changes

- Parser Expansion (Tier 1) — `backend/parsers/institution.py`
- Audit Trail — `backend/audit/audit_trail.py`, `AuditEntry` model, Alembic migration, instrumented routers, and `chain_hash` tamper-detection via `/api/audit/verify`.
- Depreciation — `backend/services/depreciation.py`, `DepreciationAsset` model/router/tests
- Hybrid Auth — `backend/auth.py` + `backend/routers/auth.py`, bcrypt + JWT
- API Utils — `backend/api_utils.py` for canonical upload/output/log paths
- Frontend auth context updated for boot/login flow
- Stage 1 research embedded in `docs/parsers/` and inline code comments

---

## v3.9 Stage 3 Changes

- **Categorization rules engine** — `backend/services/rules.py`, `backend/routers/rules.py`, `CategorizationRule` model; auto-categorizes imported transactions by pattern with priority tie-breaking.
- **CSV export** — `backend/services/export.py`, `backend/routers/export.py`; endpoints for transactions, general ledger, trial balance, P&L, and balance sheet.
- **Review flags** — `backend/services/flags.py`, `backend/routers/flags.py`, `Flag` model; flag transactions or GL entries and resolve them.
- **Workpaper references** — `workpaper_ref` column on `Transaction` and `GeneralLedgerEntry`; update endpoints on transaction and GL routers.
- **GL accounts / general ledger entries** — `GLAccount` and `GeneralLedgerEntry` models with a dedicated `backend/routers/gl.py` router.
- **Frontend smoke-test checklist** — `docs/frontend-smoke-test.md` documenting the boot/login/protected-route verification steps.

### Stage 3 API quick reference
- `POST /api/rules/?tenant_id={id}` — create categorization rule
- `GET /api/export/transactions?tenant_id={id}&start_date=...&end_date=...`
- `GET /api/export/general-ledger?tenant_id={id}`
- `GET /api/export/trial-balance?tenant_id={id}&as_of=YYYY-MM-DD`
- `GET /api/export/profit-loss?tenant_id={id}&start_date=...&end_date=...`
- `GET /api/export/balance-sheet?tenant_id={id}&as_of=YYYY-MM-DD`
- `POST /api/flags/?tenant_id={id}` — create flag
- `PUT /api/flags/{id}/resolve?tenant_id={id}` — resolve flag
- `PUT /api/transactions/{id}/workpaper-ref?tenant_id={id}` — set transaction workpaper ref
- `PUT /api/ledger/entries/{id}/workpaper-ref?tenant_id={id}` — set GL workpaper ref

---

## Privacy

All processing happens locally. Your statements, transactions, and models stay on your machine.

## Parser Security

- **Subprocess sandbox.** PDF parsing runs in a separate Python process spawned by `backend/parsers/sandbox.py`. The main FastAPI worker never loads parser libraries in-process.
- **Resource limits.** Default timeout is **30 seconds** and default memory limit is **512 MiB**. Override with `TAXFLOW_PARSER_TIMEOUT_SECONDS` and `TAXFLOW_PARSER_MAX_MEMORY_MB`.
- **Hard limits by platform.** Linux/macOS set `RLIMIT_AS`; Windows uses a working-set hint plus parent-side RSS polling and kill.
- **No traceback leakage.** Parser crashes and timeouts return a generic `422 Unprocessable Entity` with `"PDF could not be parsed safely"`. Internal details are logged server-side only.
- **OCR isolation.** The OCR parser and its heavy dependencies (`pdf2image`, `pytesseract`, `Pillow`) are loaded only inside the sandbox child.

## Security Scanning

- **Dependency vulnerability scanning (offline).** `python scripts/vuln_scan.py --db data/vuln-db.json` checks installed packages with `pip-audit --local` first, then falls back to a local JSON vulnerability database (OSV-style). It never calls external APIs unless explicitly allowed. Configure the default DB path with `TAXFLOW_VULN_DB_PATH`.
- **Secret scanning (offline).** `python scripts/secret_scan.py` scans files for potential secret-like patterns. It is conservative and intended for pre-commit / CI review, not as a replacement for human code review. Configure fail-on-find with `TAXFLOW_SECRET_SCAN_FAIL=true` and patterns with `TAXFLOW_SECRET_PATTERNS`. A pre-commit hook runs this automatically.
- **Static analysis (SAST).** `python scripts/sast_scan.py` runs Bandit against `backend/` and produces `bandit-report.json`. By default it fails only on high/critical-severity findings. Provide a baseline file via `--baseline` to suppress previously accepted low/medium noise.
- **SBOM generation.** `python scripts/sbom_generate.py` generates a deterministic CycloneDX JSON SBOM from `requirements.txt` and writes it to `shared/sbom/taxflow-pro-sbom.json`. Components are sorted and PURLs are stable so diffs are reviewable.
- **CI/pre-commit integration.** All four security scripts run in GitHub Actions and via `pre-commit`. CI fails on high/critical Bandit findings, secret leaks, or vulnerable dependencies.

### Security scripts quick reference

```bash
python scripts/secret_scan.py --fail
python scripts/sast_scan.py --baseline bandit-baseline.json
python scripts/vuln_scan.py --output vuln-report.json
python scripts/sbom_generate.py
```

## Path Safety

- **Sanitized filenames.** Every user-derived filename is passed through `backend/security/path_safety.py` before touching disk. Path separators, null bytes, control characters, reserved Windows device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9), and leading dots are stripped.
- **Base-directory enforcement.** `safe_path(base_dir, rel_path)` resolves a relative path strictly under `base_dir` and raises `ValueError` on any traversal attempt (including absolute paths and symlink escapes).
- **Upload temp files.** The upload router stores the original filename in the database but writes to a user-prefixed sanitized name on the filesystem, preventing escape from `uploads/`.
- **Export downloads.** Statement export `Content-Disposition` filenames are sanitized, and any future file-based export operations are constrained to `TAXFLOW_EXPORT_DIR` (default `exports/`) under the project root.
- **Backup/restore paths.** `scripts/backup.py` and `scripts/restore.py` validate that `--target-dir`, `--backup-dir`, and `--target-path` resolve within the project root before writing or reading.

## Backup & Restore

- **Encrypted by default:** `python scripts/backup.py` writes a `.tfebackup` file encrypted with a key derived from the current local secret via PBKDF2-HMAC-SHA256 + Fernet authenticated encryption.
- **Same-machine restore:** `python scripts/restore.py --backup-dir DIR --target-path PATH` decrypts using the same local secret. If the local secret has changed (e.g., keyring cleared or `.local_secret` regenerated), decryption fails with a clear error.
- **Self-describing format:** backup files start with a versioned header (`TFBU` magic + version + salt) so future TaxFlow versions can migrate the format.
- **Plaintext fallback (deprecated):** `scripts/backup.py --plaintext` and `scripts/restore.py --plaintext` still work for one release, but emit deprecation warnings. Use only for migration.

## Upload

- **PDF only.** The `/api/upload` endpoint rejects non-PDF extensions, non-PDF MIME types, and files that lack the `%PDF-` magic header.
- **Size limit.** Default max upload size is **32 MiB**; override with `TAXFLOW_MAX_UPLOAD_BYTES`.
- **Strict mode.** Set `TAXFLOW_UPLOAD_MAGIC_STRICT=true` to require `%PDF-1.x` or `%PDF-2.x`.
- Rejected files are never written to the parser temp directory.
