from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from .database import engine
from . import models  # noqa: F401 - ensure models are registered
from .routers import upload, clients, accounts, audit, tax, ml, export, tests, dashboard, auth
from .rls import is_postgres
from alembic.config import Config
from alembic import command
import os


def run_migrations():
    """Run Alembic migrations against the configured database engine."""
    alembic_cfg = Config(os.environ.get("ALEMBIC_CONFIG", "alembic.ini"))
    # Ensure migrations target the same database URL the app uses
    db_url = str(engine.url)
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")


run_migrations()

app = FastAPI(title="TaxFlow Pro", version="3.7.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rls_tenant_middleware(request: Request, call_next):
    """
    Capture X-Tenant-ID header for downstream PostgreSQL RLS use.
    SQLite dev/tests are unaffected because is_postgres() is False.
    When no tenant header is provided the application-level filters
    (e.g. user_id) continue to apply unchanged.
    """
    tenant_id = request.headers.get("x-tenant-id")
    if is_postgres() and tenant_id:
        try:
            request.state.tenant_id = int(tenant_id)
        except ValueError:
            request.state.tenant_id = None
    else:
        request.state.tenant_id = None
    response = await call_next(request)
    return response


app.include_router(auth.router, prefix="/api")
app.include_router(accounts.router, prefix="/api")
app.include_router(clients.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(tax.router, prefix="/api")
app.include_router(ml.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(tests.router, prefix="/api")

@app.get("/health")
def health():
    return {"status": "ok", "version": "3.7.0", "pipeline": "TaxFlow Pro"}

@app.get("/api/health")
def health_api():
    return {"status": "ok", "version": "3.7.0", "pipeline": "TaxFlow Pro"}
