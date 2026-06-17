# Getting Started with TaxFlow Pro v3.8

The fastest way to get up and running is to use the included `start.sh` script:

```bash
cd TaxFlow-Pro-v3.8
./start.sh
```

This script will:

1. Create `.env` from `.env.example` if one does not exist.
2. Create a Python virtual environment (or download a standalone Python if your
   system Python lacks `venv` support).
3. Install Python dependencies from `requirements.txt`.
4. Download a standalone Node.js if `node`/`npm` are not installed.
5. Install frontend dependencies with `npm install`.
6. Run Alembic migrations to prepare the SQLite database.
7. Start the backend on `http://localhost:8000`.
8. Start the frontend dev server on `http://localhost:3000`.

Once you see **"BOTH SERVERS RUNNING"**, open your browser to
`http://localhost:3000`.

## Requirements

- Linux, macOS, or Windows with a bash-compatible shell.
- Internet connection on first run (to download Python/Node if needed).
- `curl` or `wget` for downloading standalone toolchains.

## Manual setup

If you prefer to set things up manually:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
alembic upgrade head
source venv/bin/activate && uvicorn backend.api:app --host 0.0.0.0 --port 8000
cd frontend && npm run dev
```

See `README.md` for a full project overview.
