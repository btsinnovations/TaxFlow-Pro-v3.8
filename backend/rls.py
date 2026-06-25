"""Row-Level Security helpers for PostgreSQL tenant isolation."""
import os
from sqlalchemy import event, text
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine

from .database import DATABASE_URL, engine


def is_postgres() -> bool:
    """Return True when the configured DATABASE_URL targets PostgreSQL."""
    return bool(DATABASE_URL and DATABASE_URL.startswith("postgresql://"))


def set_tenant_on_connection(dbapi_conn, tenant_id: int) -> None:
    """Set taxflow.tenant_id on a raw DBAPI connection."""
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("SELECT set_config('taxflow.tenant_id', %s, true)", (str(tenant_id),))
    finally:
        cursor.close()


def reset_tenant_on_connection(dbapi_conn) -> None:
    """Reset taxflow.tenant_id at connection check-out when not in an explicit scope."""
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("SELECT set_config('taxflow.tenant_id', '', true)")
    finally:
        cursor.close()


def install_rls_event_listeners() -> None:
    """Attach SQLAlchemy event listeners for RLS when running on PostgreSQL."""
    if not is_postgres():
        return

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, connection_record):
        # Default to empty tenant; middleware or explicit scope will override.
        reset_tenant_on_connection(dbapi_conn)

    @event.listens_for(engine, "checkout")
    def _on_checkout(dbapi_conn, connection_record, connection_proxy):
        # Reset tenant each time a connection is checked out from the pool.
        reset_tenant_on_connection(dbapi_conn)


def _get_dbapi_connection(session: Session):
    """Return the raw DBAPI connection from a SQLAlchemy session."""
    conn = session.connection()
    # Handle both sync and the future engine/connection stack.
    raw = getattr(conn, "dbapi_connection", None)
    if raw is None:
        raw = conn.connection.dbapi_connection
    return raw


def set_tenant_id(session: Session, tenant_id: int) -> None:
    """Set the RLS tenant context for a SQLAlchemy session."""
    if not is_postgres():
        return
    dbapi_conn = _get_dbapi_connection(session)
    set_tenant_on_connection(dbapi_conn, tenant_id)


def clear_tenant_id(session: Session) -> None:
    """Clear the RLS tenant context for a SQLAlchemy session."""
    if not is_postgres():
        return
    dbapi_conn = _get_dbapi_connection(session)
    reset_tenant_on_connection(dbapi_conn)


def resolve_user_tenant_id(user) -> int:
    """Return the user's primary tenant (client) id for single-user mode.

    In tests the auth user may not have a client row yet; if the relationship is
    unloaded or empty, we query the database to ensure a client exists and
    return its id. This keeps tenant resolution deterministic for single-user
    mode without requiring every test fixture to seed a client manually.
    """
    clients = getattr(user, "clients", None)
    if clients:
        return clients[0].id

    # Fallback: inspect the ORM session to ensure a client exists.
    state = getattr(user, "_sa_instance_state", None)
    if state and state.session:
        db = state.session
        from backend import models
        client = db.query(models.Client).filter(models.Client.user_id == user.id).first()
        if client is None:
            client = models.Client(name="Default Client", user_id=user.id)
            db.add(client)
            db.commit()
            db.refresh(client)
        return client.id

    return user.id


class TenantScope:
    """Context manager to temporarily set a tenant on a SQLAlchemy session."""
    def __init__(self, session: Session, tenant_id: int):
        self.session = session
        self.tenant_id = tenant_id

    def __enter__(self):
        set_tenant_id(self.session, self.tenant_id)
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        clear_tenant_id(self.session)
        return False


async def get_current_tenant(
    request,
    current_user,
    x_tenant_id: int | None = None,
) -> int:
    """Resolve the effective tenant id for the current request.

    SQLite (single-user or not) infers the tenant from the authenticated user's
    primary client. Single-user Postgres mode also infers from the user. In
    multi-entity Postgres mode, the X-Tenant-ID header is required.
    """
    from fastapi import HTTPException
    from backend.local import settings as local_settings

    if not is_postgres() or local_settings.is_single_user():
        return resolve_user_tenant_id(current_user)

    # Multi-entity PostgreSQL: header required.
    effective_tenant_id = x_tenant_id
    if effective_tenant_id is None and request is not None:
        header_value = getattr(request, "headers", {}).get("x-tenant-id")
        if header_value is not None:
            try:
                effective_tenant_id = int(header_value)
            except (ValueError, TypeError):
                effective_tenant_id = None

    if effective_tenant_id is None:
        raise HTTPException(
            status_code=400,
            detail="X-Tenant-ID header required in multi-entity mode",
        )
    return effective_tenant_id
