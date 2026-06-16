<<<<<<< HEAD
# TaxFlow Pro Frontend

**Standalone React Web UI**

This is the frontend-only package. It provides a web interface for uploading and managing bank statements. No Python, no backend code, no OCR models.

## Quick Start

```bash
# Install
bash setup.sh

# Start dev server
bash start.sh
```

Then open http://localhost:5173

## Connecting to a Backend

The frontend needs a TaxFlow Pro backend to process statements. Configure the API URL in `.env`:

```bash
# Copy template
cp .env.example .env

# Edit .env — set your backend URL
VITE_API_BASE_URL=http://localhost:8000/api
```

### Backend Options

| Setup | URL | Use Case |
|-------|-----|----------|
| Same machine | `http://localhost:8000/api` | Running both on one computer |
| Another computer | `http://192.168.1.xxx:8000/api` | LAN access |
| Remote server | `https://api.yourdomain.com/api` | Hosted backend |

## System Requirements

- Node.js 20+
- npm 10+

## Privacy

The frontend itself is just a static web app. All statement processing happens on the **backend server** you configure in `.env`. No data is sent anywhere else.
=======
# TaxFlow Pro v3.7

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

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m alembic upgrade head
uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000
```

Default API base URL: `http://localhost:8000/api`

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
- [ ] Phase 3 — Local-first bulletproof backend (offline, encrypted SQLite, local auth, no cloud)

See `CHANGES.md` for full details.

---

## Privacy

All processing happens locally. Your statements, transactions, and models stay on your machine.
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
