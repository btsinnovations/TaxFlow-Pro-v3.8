# TaxFlow Pro v3.7 — Builder Manual

This manual explains how to build, run, validate, and understand TaxFlow Pro v3.7 from the project source. It documents the finalized **Loop 1** architecture (PostgreSQL + Alembic + tenant isolation) and the validated test results.

> **Version:** 3.7.0  
> **Project path:** `projects/TaxFlow-Pro-v3.7-main/`  
> **Last updated:** 2026-06-14

---

## 1. What This Project Is

TaxFlow Pro is a FastAPI/React application for uploading PDF bank statements, extracting transactions, categorizing them, and exporting tax-ready reports.

This repository contains:

| Layer | Location | Technology |
|-------|----------|------------|
| Backend API | `backend/` | Python, FastAPI, SQLAlchemy |
| Migrations | `alembic/` | Alembic |
| Pipeline/CLI | `phase3_pipeline/` | Python, scikit-learn, pandas |
| Frontend | `src/` (React) | React, Vite, shadcn/ui |
| Tests | `backend/tests/`, `tests/` | pytest |

> **Note:** The `README.md` and `README.txt` files predate Loop 1. They are preserved for packaging context but this manual supersedes them for builders.

---

## 2. Finalized Loop 1 Architecture

### 2.1 Persistence Layer

- **Engine:** SQLAlchemy 2.0 with ` declarative_base()`.
- **Migration manager:** Alembic.
- **Default database:** SQLite (`sqlite:///./taxflow.db`) for local development.
- **Production target:** PostgreSQL via `DATABASE_URL` in root `.env`.
- **Startup behavior:** The backend runs `alembic upgrade head` automatically when `backend/api.py` is imported. It no longer uses `Base.metadata.create_all()`.

### 2.2 Tenant Isolation Model

Loop 1 introduced a clean tenant boundary at the **client** level. Phase 2 adds PostgreSQL Row-Level Security (RLS) so tenant isolation is also enforced at the database layer when `DATABASE_URL` targets PostgreSQL.

| Design decision | Status | Details |
|-----------------|--------|---------|
| Client = tenant (entity-level) | ✅ Approved | Each row in `clients` is one tenant. |
| Multiple accounts per tenant | ✅ Approved | `accounts` has `client_id` and `tenant_id`. |
| `tenant_id` non-nullable | ✅ Approved | Present on `accounts`, `statements`, `transactions`. |
| RLS (Row-Level Security) | ✅ Done in Phase 2 | PostgreSQL policies use `current_setting('taxflow.tenant_id', true)`; SQLite dev/tests unaffected. |
| `DATABASE_URL` in root `.env` | ✅ Approved | Read via `python-dotenv` in `backend/database.py`. |
| SQLite stays default for local dev | ✅ Approved | No `.env` needed for local runs/tests. |

#### How RLS works in Phase 2

- The backend reads the `X-Tenant-ID` HTTP header in `rls_tenant_middleware` and stores it on `request.state`.
- Before each DB query, routers call `rls.set_tenant_id(session, tenant_id)` when running on PostgreSQL.
- PostgreSQL policies (`accounts_tenant_isolation_policy`, `statements_tenant_isolation_policy`, `transactions_tenant_isolation_policy`) compare the row's `tenant_id` to `current_setting('taxflow.tenant_id', true)`.
- On SQLite, `rls.is_postgres()` is `False` and tenant helpers are no-ops, so dev/tests are unchanged.

```
users
  │1:N
  ▼
clients (tenant boundary)
  │1:N
  ▼
accounts  ← tenant_id = client_id, user_id non-nullable
  │1:N
  ▼
statements  ← tenant_id = client_id, user_id non-nullable
  │1:N
  ▼
transactions  ← tenant_id = client_id
```

- Every `Account` is owned by a `User` and belongs to exactly one `Client`/tenant.
- `Account.tenant_id` is derived from `Account.client_id` on create and kept in sync on update.
- All routers that read `Statement` or `Transaction` data filter by the owning `user_id` or the tenant-scoped `tenant_id`.

### 2.3 Baseline + RLS Migrations

- File: `alembic/versions/d75a7eba9fd0_baseline_schema.py`
  - Creates all tables: `users`, `clients`, `accounts`, `statements`, `transactions`.
  - Includes Loop 1 tenant columns and indexes.
- File: `alembic/versions/b9f4e2c8d310_enable_postgresql_row_level_security.py`
  - PostgreSQL-only migration that enables RLS and creates tenant isolation policies.
  - No-op on SQLite.
- Earlier partial migration `54c037c01035` was removed to keep Alembic history clean.

---

## 3. Environment Requirements

### 3.1 System requirements

- Python 3.11+
- Node.js 20+ / npm 10+
- (Optional) PostgreSQL 14+ for production use
- (Optional) Tesseract OCR and Poppler for scanned-PDF support

### 3.2 Environment variables

Create a root `.env` file when deploying or testing against PostgreSQL:

```bash
# Database
DATABASE_URL=sqlite:///./taxflow.db          # default for local dev
# DATABASE_URL=postgresql://user:pass@localhost:5432/taxflow   # production

# Security
TAXFLOW_SECRET_KEY=change-me-in-production-2026

# Frontend (React / Vite)
VITE_API_BASE_URL=http://localhost:8000/api
```

| Variable | Required? | Where read | Purpose |
|----------|-----------|------------|---------|
| `DATABASE_URL` | No (defaults to SQLite) | `backend/database.py` | SQLAlchemy engine URL |
| `TAXFLOW_SECRET_KEY` | No (dev fallback exists) | `backend/routers/auth.py` | JWT signing key |
| `VITE_API_BASE_URL` | For frontend dev | Frontend build / `.env` | Backend API base URL |

> **Security note:** The dev fallback `SECRET_KEY` in `backend/routers/auth.py` must be overridden via `TAXFLOW_SECRET_KEY` for any non-local deployment.

---

## 4. Running the Project from Scratch

### 4.1 Quick start (local dev)

```bash
cd projects/TaxFlow-Pro-v3.7-main

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
python -m pip install -r requirements.txt

# Install frontend dependencies
npm install

# Run migrations manually (optional — backend also runs them at startup)
python -m alembic upgrade head

# Start the backend
python -m uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000

# In a separate terminal, start the frontend
npm run dev
```

- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs
- Frontend: http://localhost:5173 (Vite default) or http://localhost:3000 if using `start.sh`

### 4.2 Using the legacy `start.sh` script

`start.sh` was written before Loop 1 and still works for local dev, but it expects port `3000` for the frontend. It performs the following:

1. Creates `venv/` if missing.
2. Installs Python and npm dependencies if missing/stale.
3. Wipes `backend/api_db.json`, `backend/uploads`, `backend/output`, and `backend/logs`.
4. Starts `uvicorn backend.api:app` on port `8000`.
5. Runs `npm run dev` for the frontend.

> **Warning:** Because the backend now auto-runs Alembic migrations at import time, there is no need to call `create_all()`. `start.sh` does not need modification for Loop 1.

### 4.3 Production (PostgreSQL) setup

```bash
# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Create .env
DATABASE_URL=postgresql://taxflow:secure-password@localhost:5432/taxflow
TAXFLOW_SECRET_KEY=your-production-secret-key-min-32-characters-long

# 3. Run migrations
python -m alembic upgrade head

# 4. Start backend without --reload
python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000
```

The backend detects the `postgresql://` URL and enables a connection pool (`pool_size=5`, `max_overflow=10`, `pool_pre_ping=True`).

---

## 5. Validation & Test Results

### 5.1 Final validation run

```bash
cd projects/TaxFlow-Pro-v3.7-main
python -m pytest backend/tests/ tests/ -v
```

**Result:**

```
backend/tests/: 30 passed, 0 failed
tests/:         18 passed, 0 failed
Combined:      48 passed, 0 failed
```

### 5.2 What the backend tests cover (`backend/tests/`)

- `test_api.py`: health endpoints, CORS, auth secret key env override, registration/login, protected routes, client CRUD, account CRUD, export formats, ML status, test runner, upload rejection of non-PDFs, and parser period extraction.
- `test_parser_unification.py`: canonical parser API, institution detection, transaction builder, backend/pipeline wrapper delegation, and fallback behavior.
- `test_rls.py`: PostgreSQL detection, SQLite no-op behavior, `TenantScope` context manager, middleware `request.state` capture, and RLS migration shape.

### 5.3 What the pipeline tests cover (`tests/`)

The 18 pipeline tests validate the `phase3_package` modules, including:

- Identity/alias normalization and UID stability
- Duplicate `txn_uid` handling in `TransactionGraph`
- ML categorizer fallback when no model is present
- EU date normalization (`DD.MM.YYYY`)
- Fuel/tax classification rules
- Parser alias fixtures

See `CHANGES.md` Section 8 for the full list of pipeline fixes that unlocked these passing tests.

---

## 6. Alembic Workflow

### 6.1 Check current state

```bash
python -m alembic current
python -m alembic history
```

### 6.2 Apply migrations

```bash
python -m alembic upgrade head
```

This also happens automatically when the backend starts.

### 6.3 Create a future migration

After editing `backend/models.py`:

```bash
python -m alembic revision --autogenerate -m "describe your change"
# Review the generated file in alembic/versions/
python -m alembic upgrade head
```

> **Important:** Do not edit the baseline migration (`d75a7eba9fd0_baseline_schema.py`) once it has been applied in a shared or production database. Always create new migrations for schema changes.

---

## 7. Key API Conventions

- All routers are mounted under `/api` (e.g., `/api/clients/`, `/api/accounts/`, `/api/upload/`).
- The frontend `useAPI.ts` expects `VITE_API_BASE_URL=http://localhost:8000/api`.
- Authentication uses OAuth2 password flow: `POST /api/auth/login` returns a JWT; use `Authorization: Bearer <token>` for protected routes.
- CORS is configured for `localhost:3000`, `127.0.0.1:3000`, `localhost:5173`, and `127.0.0.1:5173`.

### 7.1 Main endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Health check |
| `POST /api/auth/register` | Create user |
| `POST /api/auth/login` | Get JWT |
| `GET /api/clients/` | List clients for current user |
| `POST /api/clients/` | Create client |
| `PATCH /api/clients/{id}` | Update client |
| `GET /api/accounts/?client_id=...` | List accounts (optionally filtered by client) |
| `POST /api/accounts/` | Create account under a client/tenant |
| `PATCH /api/accounts/{id}` | Update account (tenant_id follows client_id) |
| `POST /api/upload/` | Upload a PDF statement |
| `GET /api/export/formats` | Supported export formats |
| `GET /api/ml/status` | ML pipeline status |

---

## 8. Frontend Notes

- The frontend is a Vite + React + shadcn/ui application.
- `package.json` and `components.json` define the component registry and Tailwind configuration.
- Configure the backend URL via a root `.env`:

```bash
VITE_API_BASE_URL=http://localhost:8000/api
```

- The frontend README (`README.md`) is frontend-only and does not cover the Loop 1 backend. Use this builder manual for end-to-end setup.

---

## 9. Current Pending / Future Work

| Item | Status | Notes |
|------|--------|-------|
| PostgreSQL Row-Level Security (RLS) | ✅ Done in Phase 2 | Enforced via `X-Tenant-ID` + `taxflow.tenant_id` `set_config`; SQLite unchanged. |
| Parser unification | ✅ Done in Phase 2 | `backend/parsers/` canonical package; `phase3_pipeline/pdf_parser.py` is a thin wrapper. |
| `.env.example` file | ✅ Done | Added at project root; documents `DATABASE_URL`, `TAXFLOW_SECRET_KEY`, `VITE_API_BASE_URL`. |
| `start.sh` port note | ✅ Done | Script now prints frontend URL as `http://localhost:5173` and preserves `logs/`. |
| Configurable alias matching | Pending | Consider making `categorizer.py` alias-start matching configurable per merchant to avoid over-eager truncation. |
| Production frontend build | Pending | Add `npm run build` + static serving instructions if needed. |
| PostgreSQL RLS live validation | Pending | Policies are implemented; run against a real PostgreSQL instance to verify end-to-end tenant isolation. |
| Migration history hygiene | Done | Baseline migration is `d75a7eba9fd0_baseline_schema.py`; old partial migration removed. |

---

## 10. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: joblib` / `yaml` | Missing requirements | `python -m pip install -r requirements.txt` |
| `401` on all routes | No JWT | Register/login and send `Authorization: Bearer ...` |
| Frontend calls fail with CORS error | Wrong port/origin | Ensure frontend origin is in `allow_origins` in `backend/api.py` |
| `alembic` not found | Missing dependency | Install `requirements.txt` |
| `psycopg2` errors | Postgres driver missing | Install `psycopg2-binary` (included in requirements) |
| Tests create a `test_taxflow.db` | Test fixture uses isolated SQLite | Safe to delete after testing |

---

## 11. References

- `CHANGES.md` — Detailed change log for backend fixes, pipeline fixes, and Loop 1.
- `MIGRATIONS.md` — Alembic-specific guide.
- `backend/models.py` — SQLAlchemy tenant-isolated schema.
- `backend/database.py` — Engine configuration and `.env` loading.
- `backend/api.py` — FastAPI app, router mounts, CORS, startup migration, RLS middleware.
- `backend/rls.py` — PostgreSQL Row-Level Security helpers.
- `backend/parsers/` — Unified PDF parsing package.
- `alembic/versions/d75a7eba9fd0_baseline_schema.py` — Baseline migration.
- `alembic/versions/b9f4e2c8d310_enable_postgresql_row_level_security.py` — RLS migration.
- `backend/tests/test_api.py` — Backend API tests.
- `backend/tests/test_parser_unification.py` — Parser unification tests.
- `backend/tests/test_rls.py` — RLS tests.
