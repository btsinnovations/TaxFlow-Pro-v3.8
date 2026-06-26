from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse
from pathlib import Path
from .database import engine, DATABASE_URL
from . import models  # noqa: F401 - ensure models are registered
from .routers import upload, clients, accounts, audit, tax, tax_exports, ml, export, tests, dashboard, auth, depreciation, rules, flags, gl, transactions, health, coa, profiles, recurring, checks, inventory, fx, reconciliation, reports, budget, invoicing, liabilities, investments, imports, backup
from . import auth as auth_module
from .rls import is_postgres
from .local import settings as local_settings
from alembic.config import Config
from alembic import command
import os


ENVIRONMENT = local_settings.ENVIRONMENT


def run_migrations():
    """Run Alembic migrations against the configured database engine."""
    alembic_cfg = Config(os.environ.get("ALEMBIC_CONFIG", "alembic.ini"))
    # Ensure migrations target the same database URL the app uses
    db_url = str(engine.url)
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")


def _check_local_secret_permissions():
    """Warn if the local secret file has unsafe permissions."""
    secret_file = local_settings.LOCAL_ROOT / auth_module.LOCAL_SECRET_FILE.name
    if not secret_file.exists():
        return
    try:
        import stat
        mode = secret_file.stat().st_mode
        if os.name == "posix":
            if mode & 0o077:
                import warnings
                warnings.warn(
                    f"{secret_file} is readable or writable by group/other. "
                    "Run: chmod 600 to restrict access."
                )
        else:
            import ctypes
            path = str(secret_file.resolve())
            sd = ctypes.windll.advapi32.GetNamedSecurityInfoW(
                path, 1, 0x00000007, None, None, None, None, None
            )
            if sd is None:
                return
            import warnings
            warnings.warn(
                f"{secret_file} permissions should be restricted to the current user on Windows."
            )
    except Exception:
        pass


run_migrations()
_check_local_secret_permissions()

from backend.local.migration_health import check_migrations


def _check_migration_health():
    health = check_migrations(DATABASE_URL)
    if health["ok"]:
        return
    pending = health.get("pending", [])
    if pending:
        print("WARNING: database has pending Alembic migrations: " + repr(pending))
    else:
        print("WARNING: database migration state is stale (current=" + repr(health.get("current")) + ", latest=" + repr(health.get("latest")) + ")")
    if os.environ.get("STRICT_MIGRATIONS", "").lower() in ("1", "true", "yes"):
        raise SystemExit(1)


_check_migration_health()

# ---------------------------------------------------------------------------
# Global rate limiting (TASK-028)
# ---------------------------------------------------------------------------

from .rate_limit import GlobalRateLimiter

_GLOBAL_RATE_LIMITER = GlobalRateLimiter.from_env()


class _GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """Apply a sliding-window per-IP rate limit to all requests."""

    async def dispatch(self, request: StarletteRequest, call_next):
        # Tests bypass the limiter unless they explicitly flag the current
        # instance for enforcement (see backend.tests.test_global_rate_limit).
        if os.environ.get("TAXFLOW_TESTING") and not getattr(_GLOBAL_RATE_LIMITER, "_test_enforce", False):
            return await call_next(request)

        remote_addr = request.client.host if request.client else None
        try:
            _GLOBAL_RATE_LIMITER.check(remote_addr, dict(request.headers))
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers,
            )
        return await call_next(request)


# ---------------------------------------------------------------------------
# App factory + middleware stack
# ---------------------------------------------------------------------------


def _read_version() -> str:
    """Read canonical version from project root."""
    root = Path(__file__).resolve().parents[1]
    version_file = root / "version.txt"
    try:
        return version_file.read_text().strip()
    except FileNotFoundError:
        return "0.0.0"


app = FastAPI(title="TaxFlow Pro", version=_read_version())

# Global rate limit runs very early so abuse is rejected before request work.
app.add_middleware(_GlobalRateLimitMiddleware)


# ---------------------------------------------------------------------------
# CORS hardening
# ---------------------------------------------------------------------------

def _get_cors_origins() -> list[str]:
    """Return the explicit allow-list for CORS origins.

    Defaults to common local frontend dev ports. Override with a comma-
    separated list in ``TAXFLOW_CORS_ORIGINS``. Empty strings and surrounding
    whitespace are ignored. Credentials are only sent to these exact origins.
    """
    env_origins = os.environ.get("TAXFLOW_CORS_ORIGINS", "").strip()
    if env_origins:
        return [o.strip() for o in env_origins.split(",") if o.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


CORS_ORIGINS = _get_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["authorization", "content-type", "x-tenant-id", "x-requested-with"],
    expose_headers=["x-request-id"],
    max_age=600,
)


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add baseline security headers to every HTTP response."""

    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        # CSP is intentionally minimal for a JSON API; no inline scripts/styles.
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
        # HSTS is only meaningful over HTTPS; enable it in production.
        if ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(_SecurityHeadersMiddleware)


# ---------------------------------------------------------------------------
# Request size limit (TASK-031)
# ---------------------------------------------------------------------------

class _RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject request bodies larger than the configured general body limit.

    Multipart uploads to /api/upload are still governed by the upload-specific
    limit in backend.security.upload_validator; this middleware applies a 10 MiB
    default to all other routes and rejects early via Content-Length.
    """

    async def dispatch(self, request: StarletteRequest, call_next):
        # Import inside dispatch so tests can monkeypatch backend.security.request_validation.
        from .security.request_validation import MAX_BODY_SIZE_BYTES, human_size

        # Upload route uses its own validator.
        if request.url.path == "/api/upload":
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length is not None:
            size = None
            try:
                size = int(content_length)
            except ValueError:
                pass

            # Strict validation: Content-Length must be a non-negative integer.
            if size is None or size < 0:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                )

            if size > MAX_BODY_SIZE_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            f"Request body exceeds maximum size of "
                            f"{MAX_BODY_SIZE_BYTES} bytes ({human_size(MAX_BODY_SIZE_BYTES)})"
                        )
                    },
                    headers={"Retry-After": str(MAX_BODY_SIZE_BYTES)},
                )
        return await call_next(request)


app.add_middleware(_RequestSizeLimitMiddleware)


@app.middleware("http")
async def rls_tenant_middleware(request: Request, call_next):
    """
    Capture X-Tenant-ID header for downstream PostgreSQL RLS use.

    SQLite dev/tests are unaffected because is_postgres() is False. In
    single-user mode the tenant is inferred from the authenticated user's
    primary client, so the header is optional. In multi-entity Postgres mode
    the header remains required and is resolved by get_current_tenant.
    """
    tenant_id = request.headers.get("x-tenant-id")
    if is_postgres() and not local_settings.is_single_user():
        if tenant_id is None:
            return JSONResponse(
                status_code=400,
                content={"detail": "X-Tenant-ID header required in multi-entity mode"},
            )
        try:
            request.state.tenant_id = int(tenant_id)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid X-Tenant-ID header"},
            )
    elif is_postgres():
        # Postgres but single-user: still honor the header if present.
        try:
            request.state.tenant_id = int(tenant_id) if tenant_id is not None else None
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid X-Tenant-ID header"},
            )
    else:
        request.state.tenant_id = None
    return await call_next(request)


app.include_router(auth.router, prefix="/api")
app.include_router(accounts.router, prefix="/api")
app.include_router(clients.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(coa.router, prefix="/api")
app.include_router(profiles.router, prefix="/api")
app.include_router(recurring.router, prefix="/api")
app.include_router(checks.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(fx.router, prefix="/api")
app.include_router(reconciliation.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(budget.router, prefix="/api")
app.include_router(invoicing.router, prefix="/api")
app.include_router(liabilities.router, prefix="/api")
app.include_router(investments.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(imports.router, prefix="/api")
app.include_router(backup.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(tax.router, prefix="/api")
app.include_router(tax_exports.router, prefix="/api")
app.include_router(ml.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(depreciation.router, prefix="/api")
app.include_router(rules.router, prefix="/api")
app.include_router(rules.tax_rules_router, prefix="/api")
app.include_router(flags.router, prefix="/api")
app.include_router(gl.router, prefix="/api")
app.include_router(health.router, prefix="/api")
if ENVIRONMENT == "development":
    app.include_router(tests.router, prefix="/api")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": _read_version(),
        "pipeline": "TaxFlow Pro",
        "runtime_mode": local_settings.RUNTIME_MODE,
        "offline": local_settings.is_offline(),
        "single_user": local_settings.is_single_user(),
        "multi_entity": getattr(local_settings, "TAXFLOW_MULTI_ENTITY", False),
    }

@app.get("/api/health")
def health_api():
    from backend.local.bootstrap import run_bootstrap
    report = run_bootstrap()
    return {
        "status": "ok",
        "version": _read_version(),
        "pipeline": "TaxFlow Pro",
        "runtime_mode": local_settings.RUNTIME_MODE,
        "offline": local_settings.is_offline(),
        "single_user": local_settings.is_single_user(),
        "multi_entity": getattr(local_settings, "TAXFLOW_MULTI_ENTITY", False),
        "bootstrap_ready": report.ready,
        "bootstrap_checks": [
            {"name": c.name, "available": c.available, "required": c.required, "message": c.message}
            for c in report.checks
        ],
    }

# ---------------------------------------------------------------------------
# Static frontend serving (Phase 2 packaging)
#
# We cannot mount StaticFiles at "/" because Starlette Mount routes own every
# path under their prefix. For non-GET/HEAD requests to API paths that do not
# exist as static files (e.g. POST /api/upload), the mounted StaticFiles app
# returns 405 Method Not Allowed before FastAPI can route to the API handler.
#
# The standard FastAPI SPA pattern is therefore used instead:
#   1. Serve hashed assets from /assets.
#   2. Catch non-API 404 responses in middleware and return index.html.
# This satisfies the same acceptance criteria (root serves the SPA, deep
# links fallback to index.html, /api/* and /health remain authoritative).
# ---------------------------------------------------------------------------

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
        name="assets",
    )


class _SPAFallbackMiddleware(BaseHTTPMiddleware):
    """Return the SPA index.html for any non-API 404 on a browser route."""

    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        if response.status_code != 404:
            return response
        path = request.url.path
        # API, static assets, and the top-level health endpoint must not be
        # swallowed by the SPA fallback.
        if path.startswith("/api/") or path.startswith("/assets/") or path == "/health":
            return response
        index_path = _FRONTEND_DIST / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return response


app.add_middleware(_SPAFallbackMiddleware)


if __name__ == "__main__":

    import uvicorn
    # Default to localhost-only binding for local-first safety. LAN/opt-in
    # binding is enabled via TAXFLOW_BIND_LAN=true or UVICORN_HOST override.
    default_host = "127.0.0.1"
    if os.environ.get("TAXFLOW_BIND_LAN", "").lower() in ("1", "true", "yes"):
        default_host = "0.0.0.0"
    host = os.environ.get("UVICORN_HOST", default_host)
    port = int(os.environ.get("UVICORN_PORT", "8000"))
    uvicorn.run("backend.api:app", host=host, port=port, reload=True)
