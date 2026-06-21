# Getting Started with TaxFlow Pro v3.7

This guide walks you through running TaxFlow Pro for the first time.

---

## 1. Requirements

- Python 3.11 or newer
- Node.js 20 or newer
- npm 10 or newer

Optional for production:
- PostgreSQL 14 or newer
- Tesseract OCR and Poppler for scanned PDFs

---

## 2. Install Dependencies

Open a terminal in the project folder and run:

```bash
python -m pip install -r requirements.txt
npm install
```

This installs the Python backend, the pipeline/CLI tools, and the React frontend.

---

## 3. Configure Environment Variables

Create a `.env` file at the project root:

```bash
cp .env.example .env
```

For local development, the defaults are fine. The backend will use SQLite automatically.

```bash
# Optional: use PostgreSQL instead of SQLite
# DATABASE_URL=postgresql://user:password@localhost:5432/taxflow

# Optional: override the default JWT signing key
# TAXFLOW_SECRET_KEY=your-production-secret-key-min-32-characters-long

# Frontend API base URL
VITE_API_BASE_URL=http://localhost:8000/api
```

---

## 4. Run the Backend

```bash
python -m uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000
```

The backend auto-runs Alembic migrations at startup.

- API base URL: http://localhost:8000/api
- Interactive docs: http://localhost:8000/docs

---

## 5. Run the Frontend

In a second terminal:

```bash
npm run dev
```

Then open http://localhost:5173 in your browser.

---

## 6. Create Your First User

Use the API docs or the frontend to register an account:

```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secure-password"}'
```

Then log in to receive a JWT token.

---

## 7. Upload a Bank Statement

1. Log in on the frontend.
2. Create a client and an account.
3. Drag a PDF statement into the upload area and process it.
4. Review extracted transactions, categories, and exports.

---

## 8. Run the Test Suite

```bash
python -m pytest backend/tests/ tests/ -v
```

Expected: all tests pass.

---

## 9. Next Steps

- Read `BUILDER_MANUAL.md` for architecture details.
- Read `MIGRATIONS.md` before making database changes.
- Read `TROUBLESHOOTING.md` if something goes wrong.
