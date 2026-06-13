#!/usr/bin/env python3
"""
TaxFlow Pro - FastAPI Backend
Wraps the Financial ETL Pipeline for non-technical users.
"""

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure pipeline is importable
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from routers import upload, clients, accounts, audit, tax, ml, export, tests, dashboard, auth
from api_models import HealthResponse
from api_utils import ensure_dirs


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    ensure_dirs()
    yield


app = FastAPI(
    title="TaxFlow Pro API",
    description="Financial ETL Pipeline REST API for non-technical users",
    version="3.6.0",
    lifespan=lifespan,
)

# CORS - allow the React dev server and production builds
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload.router, prefix="/api/upload", tags=["Upload & Process"])
app.include_router(clients.router, prefix="/api/clients", tags=["Client Management"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["Account Management"])
app.include_router(audit.router, prefix="/api/audit", tags=["Audit Trail"])
app.include_router(tax.router, prefix="/api/tax", tags=["Tax Rules"])
app.include_router(ml.router, prefix="/api/ml", tags=["ML Training"])
app.include_router(export.router, prefix="/api/export", tags=["Export"])
app.include_router(tests.router, prefix="/api/tests", tags=["Test Suite"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])


@app.get("/", response_model=HealthResponse)
async def root():
    return HealthResponse(status="ok", version="3.6.0", pipeline="TaxFlow Pro")


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", version="3.6.0", pipeline="TaxFlow Pro")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
