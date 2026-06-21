# TaxFlow Pro v3.7 — Troubleshooting

Common problems and how to fix them.

---

## Installation Issues

### `ModuleNotFoundError: joblib`, `yaml`, `httpx`, etc.

Dependencies are missing. Install them:

```bash
python -m pip install -r requirements.txt
```

---

## Backend Issues

### Backend won't start

Check that migrations can run:

```bash
python -m alembic upgrade head
```

If this fails, verify your `DATABASE_URL` in `.env` and that PostgreSQL is reachable (if using PostgreSQL).

---

### `401 Unauthorized` on all routes

You need to log in and send a Bearer token. Steps:

1. Register a user:
   ```bash
   curl -X POST "http://localhost:8000/api/auth/register" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com", "password": "password"}'
   ```

2. Log in to get a token:
   ```bash
   curl -X POST "http://localhost:8000/api/auth/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=user@example.com&password=password"
   ```

3. Use the token:
   ```bash
   curl -H "Authorization: Bearer <your-token>" http://localhost:8000/api/clients/
   ```

---

### `SECRET_KEY` warning

The dev fallback key must be overridden in production. Set in `.env`:

```bash
TAXFLOW_SECRET_KEY=your-production-secret-key-min-32-characters-long
```

---

## Frontend Issues

### Frontend cannot reach backend (CORS error)

Make sure the frontend origin is allowed in `backend/api.py` and that `VITE_API_BASE_URL` in `.env` matches the backend URL.

Default allowed origins include:
- http://localhost:3000
- http://127.0.0.1:3000
- http://localhost:5173
- http://127.0.0.1:5173

---

### Frontend shows blank page or 404

Confirm the backend is running and the frontend `VITE_API_BASE_URL` is set correctly. Then restart the frontend dev server.

---

## Database Issues

### PostgreSQL connection errors

Verify PostgreSQL is running and the `DATABASE_URL` is correct:

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/taxflow
```

Make sure `psycopg2-binary` is installed (included in `requirements.txt`).

---

### SQLite locked errors

Avoid opening the same SQLite file from multiple processes. If using WAL mode, transactions should clear quickly. Restarting the backend usually resolves temporary locks.

---

## PDF / Parser Issues

### Statement fails to parse

- Ensure the file is a PDF.
- For scanned PDFs, install Tesseract OCR and Poppler.
- Check `logs/` for parser error details.
- Try the generic parser path via the API docs.

---

## Test Issues

### Tests fail after pulling new code

Update dependencies and re-run migrations:

```bash
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m pytest backend/tests/ tests/ -v
```

---

## Still Stuck?

Open `BUILDER_MANUAL.md` for deeper architecture details or check `CHANGES.md` for recent fixes.
