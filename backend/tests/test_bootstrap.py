"""Tests for offline bootstrap / local dependency checks (TASK-038.7)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from backend.local.bootstrap import run_bootstrap, BootstrapCheck
from backend.api import app


client = TestClient(app)


def test_bootstrap_returns_report():
    report = run_bootstrap()
    assert isinstance(report.ready, bool)
    assert len(report.checks) > 0
    names = {c.name for c in report.checks}
    assert "module:fastapi" in names
    assert "database:sqlite" in names


def test_bootstrap_report_serializes():
    report = run_bootstrap()
    data = report.to_dict()
    assert "ready" in data
    assert "checks" in data
    assert all("name" in c and "available" in c for c in data["checks"])


def test_bootstrap_endpoint():
    response = client.get("/api/health/bootstrap")
    assert response.status_code == 200
    data = response.json()
    assert "ready" in data
    assert isinstance(data["ready"], bool)
    assert len(data["checks"]) > 0


def test_health_includes_bootstrap():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "bootstrap_ready" in data
    assert "bootstrap_checks" in data
