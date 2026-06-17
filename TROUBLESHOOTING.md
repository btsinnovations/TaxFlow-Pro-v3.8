# TaxFlow Pro v3.8 — Troubleshooting

## The app won't start

Run `./start.sh` from the project root. The script prints progress messages and
will tell you if a step failed. Common causes:

- **No internet on first run** — the bootstrapper may need to download a
  standalone Python or Node.js toolchain.
- **Permission denied** — make sure `start.sh` is executable:
  `chmod +x start.sh`.
- **Port already in use** — stop any process using ports `8000` or `3000`.

## Registration returns 500

This usually means the database schema is out of sync. Delete the local SQLite
database and let Alembic recreate it:

```bash
rm -f taxflow.db
alembic upgrade head
```

## Login fails with 422

The backend expects JSON (`{"username": "...", "password": "..."}`) on
`POST /api/auth/login`. If you are testing with `curl`, send
`-H "Content-Type: application/json"`.

## Authenticated endpoints return 401

The frontend `useAPI.ts` attaches the Bearer token automatically. If you see
401s in the browser, check that:

1. Login succeeded and returned an `access_token`.
2. `localStorage` contains a `token` item.
3. The API call includes `Authorization: Bearer <token>`.

## Frontend shows old mock data

Some sections (e.g., Test Suite) previously read from `mockData.ts`. After the
remediation, the Test Suite fetches live results from `/api/tests`. If a page
still shows stale data, hard-refresh the browser.

## Still stuck?

Open the browser's developer tools (Network tab) and the backend terminal output
(`logs/startup.log` if you used `start.sh`). Those are the fastest places to
find the exact error.
