"""SQLite application-level tenant scoping tests.

Verifies:
- ``backend.rls`` helpers are no-ops on SQLite.
- Router queries only return data scoped to the active tenant (client).
- A row created under tenant A is not visible when the active context is tenant B.
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_sqlite_rls_helpers_noop():
    """RLS helpers must not raise and must short-circuit on SQLite."""
    from backend import rls

    assert rls.is_postgres() is False
    # set_tenant_id / clear_tenant_id should be no-ops and not raise.
    rls.set_tenant_id(None, 1)  # type: ignore[arg-type]
    rls.clear_tenant_id(None)  # type: ignore[arg-type]


SMOKE_PASSWORD = "RLS-Test-Pass-2026!"


def test_accounts_router_scopes_by_active_tenant(client: "TestClient") -> None:
    """Account list only returns accounts for the active tenant."""
    # Boot and log in as admin.
    boot = client.post("/api/auth/boot", json={"password": SMOKE_PASSWORD})
    assert boot.status_code in (200, 201), boot.text
    token = boot.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # Create two clients (tenants) for the same user.
    a = client.post("/api/clients", json={"name": "Tenant A", "email": "a@example.com", "tax_id": "111-11-1111"}, headers=auth)
    b = client.post("/api/clients", json={"name": "Tenant B", "email": "b@example.com", "tax_id": "222-22-2222"}, headers=auth)
    assert a.status_code in (200, 201), a.text
    assert b.status_code in (200, 201), b.text
    tenant_a = a.json()["id"]
    tenant_b = b.json()["id"]

    # Create an account under tenant A.
    acct_a = client.post(
        "/api/accounts",
        json={"name": "Acct A", "institution": "Bank A", "account_number_masked": "1111", "type": "checking", "client_id": tenant_a},
        headers=auth,
    )
    assert acct_a.status_code in (200, 201), acct_a.text

    # Create an account under tenant B.
    acct_b = client.post(
        "/api/accounts",
        json={"name": "Acct B", "institution": "Bank B", "account_number_masked": "2222", "type": "checking", "client_id": tenant_b},
        headers=auth,
    )
    assert acct_b.status_code in (200, 201), acct_b.text

    # Query accounts scoped to tenant A.
    list_a = client.get("/api/accounts", params={"tenant_id": tenant_a}, headers=auth)
    assert list_a.status_code == 200, list_a.text
    ids_a = {x["id"] for x in list_a.json()}
    assert acct_a.json()["id"] in ids_a
    assert acct_b.json()["id"] not in ids_a

    # Query accounts scoped to tenant B.
    list_b = client.get("/api/accounts", params={"tenant_id": tenant_b}, headers=auth)
    assert list_b.status_code == 200, list_b.text
    ids_b = {x["id"] for x in list_b.json()}
    assert acct_b.json()["id"] in ids_b
    assert acct_a.json()["id"] not in ids_b


def test_transactions_router_scopes_by_active_tenant(client: "TestClient") -> None:
    """Transaction list only returns transactions for the active tenant."""
    boot = client.post("/api/auth/boot", json={"password": SMOKE_PASSWORD})
    assert boot.status_code in (200, 201), boot.text
    token = boot.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    a = client.post("/api/clients", json={"name": "Tenant A2", "email": "a2@example.com", "tax_id": "333-33-3333"}, headers=auth)
    b = client.post("/api/clients", json={"name": "Tenant B2", "email": "b2@example.com", "tax_id": "444-44-4444"}, headers=auth)
    assert a.status_code in (200, 201) and b.status_code in (200, 201)
    tenant_a = a.json()["id"]
    tenant_b = b.json()["id"]

    acct_a = client.post("/api/accounts", json={"name": "Acct A2", "institution": "Bank", "account_number_masked": "3333", "type": "checking", "client_id": tenant_a}, headers=auth)
    acct_b = client.post("/api/accounts", json={"name": "Acct B2", "institution": "Bank", "account_number_masked": "4444", "type": "checking", "client_id": tenant_b}, headers=auth)
    assert acct_a.status_code in (200, 201) and acct_b.status_code in (200, 201)

    tx_a = client.post("/api/transactions", json={"account_id": acct_a.json()["id"], "description": "Rent", "amount": 1000.0, "tx_type": "debit", "date": "2026-01-01", "category": "Rent"}, params={"tenant_id": tenant_a}, headers=auth)
    tx_b = client.post("/api/transactions", json={"account_id": acct_b.json()["id"], "description": "Payroll", "amount": 2000.0, "tx_type": "credit", "date": "2026-01-02", "category": "Income"}, params={"tenant_id": tenant_b}, headers=auth)
    assert tx_a.status_code in (200, 201) and tx_b.status_code in (200, 201)

    list_a = client.get("/api/transactions", params={"tenant_id": tenant_a, "limit": 100}, headers=auth)
    assert list_a.status_code == 200
    ids_a = {x["id"] for x in list_a.json()}
    assert tx_a.json()["id"] in ids_a
    assert tx_b.json()["id"] not in ids_a

    list_b = client.get("/api/transactions", params={"tenant_id": tenant_b, "limit": 100}, headers=auth)
    assert list_b.status_code == 200
    ids_b = {x["id"] for x in list_b.json()}
    assert tx_b.json()["id"] in ids_b
    assert tx_a.json()["id"] not in ids_b
