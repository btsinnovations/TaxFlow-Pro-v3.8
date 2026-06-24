"""Recurring / scheduled transaction rule API endpoints for TaxFlow Pro v3.10."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.routers.auth import get_current_user
from backend.database import get_db
from backend.schemas import RecurringRuleCreate, RecurringRuleUpdate, RecurringRule

router = APIRouter(prefix="/api/recurring", tags=["recurring"])


@router.get("/", response_model=list[RecurringRule])
def list_rules(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """List recurring transaction rules."""
    raise NotImplementedError("TASK-3.10.04")


@router.post("/", response_model=RecurringRule)
def create_rule(payload: RecurringRuleCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Create a recurring transaction rule."""
    raise NotImplementedError("TASK-3.10.04")


@router.put("/{rule_id}", response_model=RecurringRule)
def update_rule(rule_id: int, payload: RecurringRuleUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Update a recurring transaction rule."""
    raise NotImplementedError("TASK-3.10.04")


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Soft-delete a recurring rule."""
    raise NotImplementedError("TASK-3.10.04")


@router.post("/{rule_id}/generate")
def generate_instances(rule_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Generate transaction instances for a rule (app-open behavior)."""
    raise NotImplementedError("TASK-3.10.04")
