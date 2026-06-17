from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from .database import engine
from . import models  # noqa: F401 - ensure models are registered
from .routers import (
    upload, clients, accounts, audit, tax, ml, export, tests, dashboard, auth,
    journal_entries, reports_signed, archive, exports_tax,
    transactions_notes_flags, transactions_list, ofx, engagement,
    batch_import, receipts, forecast, settings, budget, exchange_rates,
    depreciation, periods, reclassify,
)
from .rls import is_postgres
from alembic.config import Config
from alembic import command
import os
import asyncio


def run_migrations():
    """Run Alembic migrations against the configured database engine."""
    alembic_cfg = Config(os.environ.get("ALEMBIC_CONFIG", "alembic.ini"))
    # Ensure migrations target the same database URL the app uses
    db_url = str(engine.url)
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")


run_migrations()

app = FastAPI(title="TaxFlow Pro", version="3.8.0")


@app.on_event("startup")
async def startup_event():
    """Ensure all SQLAlchemy model tables exist (safety net for SQLite dev)."""
    models.Base.metadata.create_all(bind=engine)


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


# Core routers
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

# v3.8 extended routers
app.include_router(journal_entries.router, prefix="/api")
app.include_router(reports_signed.router, prefix="/api")
app.include_router(archive.router, prefix="/api")
app.include_router(exports_tax.router, prefix="/api")
app.include_router(transactions_notes_flags.router, prefix="/api")
app.include_router(transactions_list.router, prefix="/api")
app.include_router(ofx.router, prefix="/api")
app.include_router(engagement.router, prefix="/api")
app.include_router(batch_import.router, prefix="/api")
app.include_router(receipts.router, prefix="/api")
app.include_router(forecast.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(budget.router, prefix="/api")
app.include_router(exchange_rates.router, prefix="/api")
app.include_router(depreciation.router, prefix="/api")
app.include_router(periods.router, prefix="/api")
app.include_router(reclassify.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "version": "3.8.0", "pipeline": "TaxFlow Pro"}


@app.get("/api/health")
def health_api():
    return {"status": "ok", "version": "3.8.0", "pipeline": "TaxFlow Pro"}


# ------------------------------------------------------------------
# SSE event stream endpoint
# ------------------------------------------------------------------

@app.get("/api/events")
async def event_stream():
    """Server-Sent Events endpoint for real-time notifications."""
    async def generate():
        while True:
            await asyncio.sleep(30)
            yield f"data: {{'type': 'heartbeat', 'timestamp': '{__import__('datetime').datetime.now().isoformat()}'}}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")


# ------------------------------------------------------------------
# Firm logo endpoint
# ------------------------------------------------------------------

@app.get("/api/firm-logo")
def firm_logo():
    """Serve the firm logo file if configured."""
    logo_path = os.environ.get("FIRM_LOGO_PATH")
    if logo_path and os.path.isfile(logo_path):
        return FileResponse(logo_path)
    return {"detail": "No logo configured"}


# ------------------------------------------------------------------
# SPA static file serving (for production builds)
# ------------------------------------------------------------------

_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(_frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index_file = os.path.join(_frontend_dist, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"detail": "Frontend not built"}
