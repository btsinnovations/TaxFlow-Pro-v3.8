# TaxFlow Pro v3.7 — Migrations Guide

This project uses [Alembic](https://alembic.sqlalchemy.org/) for SQLAlchemy schema migrations.

## Default behavior

- `DATABASE_URL` is read from the root `.env` file (via `python-dotenv`).
- If `DATABASE_URL` is unset, the default is `sqlite:///./taxflow.db`.
- The backend runs `alembic upgrade head` automatically at startup instead of calling `Base.metadata.create_all()`.

## Important: baseline migration

The current baseline migration (`d75a7eba9fd0_baseline_schema`) creates all tables from scratch, including the tenant-isolation columns introduced in Loop 1:

- `tenant_id` on `accounts`, `statements`, `transactions`
- `user_id` on `statements`
- Non-nullable `client_id`/`user_id` on `accounts`
- Tenant indexes on each table

Because this is a development/evaluation build, the baseline migration is clean. In a production environment that already contains data, you would normally create an initial migration with `alembic revision --autogenerate -m "baseline"` from the existing schema, then add a second migration for tenant columns. Here we started from an empty schema and folded the tenant work into the baseline.

## Running migrations manually

```bash
cd projects/TaxFlow-Pro-v3.7-main
python -m alembic upgrade head
```

To inspect the current revision:

```bash
python -m alembic current
python -m alembic history
```

## Adding future migrations

1. Edit `backend/models.py` to add/change columns, indexes, or tables.
2. Generate a migration:

```bash
python -m alembic revision --autogenerate -m "describe your change"
```

3. Review the generated file in `alembic/versions/` before applying it.
4. Apply it:

```bash
python -m alembic upgrade head
```

Do **not** edit the baseline migration once it has been applied in any shared/production database. Create new migrations for all future schema changes.

## Switching to PostgreSQL

Set `DATABASE_URL` in `.env`:

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/taxflow
TAXFLOW_SECRET_KEY=your-production-secret
```

Then install the backend dependencies and run migrations:

```bash
python -m pip install -r requirements.txt
python -m alembic upgrade head
```

The backend will detect the `postgresql://` URL and use a connection pool appropriate for PostgreSQL.

## RLS migration

The second migration (`b9f4e2c8d310_enable_postgresql_row_level_security.py`) is PostgreSQL-only:

- Enables `ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY` on `accounts`, `statements`, and `transactions`.
- Creates a helper function `taxflow.tenant_id_matches(integer)` that compares the row's `tenant_id` to `current_setting('taxflow.tenant_id', true)`.
- Creates `*_tenant_isolation_policy` policies for `ALL` operations with `USING` and `WITH CHECK` clauses.
- On SQLite the migration is a no-op.

To verify RLS against a real PostgreSQL instance:

```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/taxflow python -m alembic upgrade head
```

Then run the backend and make requests with the `X-Tenant-ID` header.

## Dev/test SQLite

No `.env` configuration is needed. The backend falls back to `sqlite:///./taxflow.db` and uses SQLite-compatible engine arguments automatically. The test suite (`backend/tests/conftest.py`) uses its own isolated SQLite database.

## Tenant isolation design

- Tenant boundary is `client_id`. Each client row is a tenant.
- `tenant_id` on `accounts`, `statements`, and `transactions` is a foreign key to `clients.id` and is non-nullable.
- Application code filters by `tenant_id` (or the owning `user_id`) in every query.
- PostgreSQL Row-Level Security (RLS) is implemented in migration `b9f4e2c8d310_enable_postgresql_row_level_security.py` and is automatically active when `DATABASE_URL` starts with `postgresql://`.
- RLS policies use `current_setting('taxflow.tenant_id', true)` and are transparent to SQLite dev/test environments.
