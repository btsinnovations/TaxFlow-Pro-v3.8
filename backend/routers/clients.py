"""
Client management endpoints.
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from typing import List
from api_models import ClientCreate, ClientOut
from api_utils import get_db, save_db, log_event

router = APIRouter()


@router.get("/", response_model=List[ClientOut])
async def list_clients():
    db = get_db()
    clients = db.get("clients", {})
    result = []
    for cid, c in clients.items():
        stmt_count = sum(
            1 for p in db.get("processed_files", {}).values()
            if p.get("client_id") == cid
        )
        result.append(ClientOut(
            id=cid,
            name=c["name"],
            entity_type=c.get("entity_type", "Individual"),
            tax_id=c.get("tax_id"),
            notes=c.get("notes"),
            created_at=c.get("created_at", ""),
            statement_count=stmt_count,
            is_active=c.get("is_active", True),
        ))
    return result


@router.post("/", response_model=ClientOut)
async def create_client(client: ClientCreate):
    db = get_db()
    cid = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    db["clients"][cid] = {
        "id": cid,
        "name": client.name,
        "entity_type": client.entity_type,
        "tax_id": client.tax_id,
        "notes": client.notes,
        "created_at": now,
        "is_active": True,
    }
    save_db(db)
    log_event("INFO", "CLIENT_CREATED", f"Created client: {client.name}", client_id=cid)
    return ClientOut(
        id=cid,
        name=client.name,
        entity_type=client.entity_type,
        tax_id=client.tax_id,
        notes=client.notes,
        created_at=now,
        statement_count=0,
        is_active=True,
    )


@router.get("/{client_id}", response_model=ClientOut)
async def get_client(client_id: str):
    db = get_db()
    c = db.get("clients", {}).get(client_id)
    if not c:
        raise HTTPException(404, f"Client {client_id} not found")
    stmt_count = sum(
        1 for p in db.get("processed_files", {}).values()
        if p.get("client_id") == client_id
    )
    return ClientOut(
        id=client_id,
        name=c["name"],
        entity_type=c.get("entity_type", "Individual"),
        tax_id=c.get("tax_id"),
        notes=c.get("notes"),
        created_at=c.get("created_at", ""),
        statement_count=stmt_count,
        is_active=c.get("is_active", True),
    )


@router.delete("/{client_id}")
async def delete_client(client_id: str):
    db = get_db()
    if client_id not in db.get("clients", {}):
        raise HTTPException(404, f"Client {client_id} not found")
    del db["clients"][client_id]
    save_db(db)
    log_event("INFO", "CLIENT_DELETED", f"Deleted client {client_id}")
    return {"success": True, "message": f"Client {client_id} deleted"}
