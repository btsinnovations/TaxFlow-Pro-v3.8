# TaxFlow Pro v3.8

Local-first, offline-capable financial document processing for individuals and small businesses.

TaxFlow Pro ingests bank statements and financial documents, extracts transactions, categorizes them, and produces tax-ready exports — without ever sending your data to the cloud.

---

## What It Does

- **PDF statement parsing** — extracts transactions, balances, dates, and account metadata.
- **Local ML categorization** — trains and predicts on your own data; no cloud ML APIs.
- **Multi-account, multi-client** — manage personal and business accounts in one place.
- **Tax-ready exports** — CSV, JSON, QIF, QBO, Xero, Excel, PDF summary, and Parquet.
- **Offline by default** — no Plaid, no live bank feeds, no telemetry, no internet required.

---

## Quick Start

Run the bootstrap script from the project root:

```bash
./start.sh
```

`start.sh` creates the Python virtual environment, installs dependencies, prepares the database, installs frontend packages, and starts both the backend and frontend dev servers.

Then open http://localhost:3000.

Default API base URL: `http://localhost:8000/api`

---

## Configuration

Copy `.env.example` to `.env` and set:

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | Database connection | `sqlite:///./taxflow.db` |
| `TAXFLOW_SECRET_KEY` | JWT signing secret | dev fallback |
| `ALEMBIC_CONFIG` | Path to `alembic.ini` | `alembic.ini` |

---

## Running Tests

```bash
python -m pytest backend/tests tests -v
```

Expected: **48 passed, 0 failed**

---

## Architecture

- **Backend:** FastAPI + SQLAlchemy + Alembic
- **Database:** SQLite default; optional local PostgreSQL
- **Frontend:** React + Vite
- **ML:** scikit-learn (TF-IDF + LogisticRegression) running locally
- **Packaging:** Browser + local server (Windows / macOS / Linux)

---

## Roadmap

- [x] Loop 1 — PostgreSQL + Alembic + tenant isolation
- [x] Phase 2 — Parser unification + PostgreSQL Row-Level Security
- [x] Phase 3 — Local-first bulletproof backend (offline, encrypted SQLite, local auth, no cloud)

See `CHANGES.md` for full details.

---

## Privacy

All processing happens locally. Your statements, transactions, and models stay on your machine.
