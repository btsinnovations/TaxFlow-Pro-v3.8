"""Profile role membership API endpoints for TaxFlow Pro v3.10."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.routers.auth import get_current_user
from backend.database import get_db
from backend.schemas import ProfileMembershipCreate, ProfileMembershipUpdate, ProfileMembershipOut

router = APIRouter(prefix="/api/profiles/{profile_id}/members", tags=["profiles"])


@router.get("/", response_model=list[ProfileMembershipOut])
def list_members(profile_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """List members of a profile."""
    raise NotImplementedError("TASK-3.10.02")


@router.post("/", response_model=ProfileMembershipOut)
def add_member(profile_id: int, payload: ProfileMembershipCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Add a user to a profile with a role."""
    raise NotImplementedError("TASK-3.10.02")


@router.put("/{membership_id}", response_model=ProfileMembershipOut)
def update_member(profile_id: int, membership_id: int, payload: ProfileMembershipUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Update a member's role."""
    raise NotImplementedError("TASK-3.10.02")


@router.delete("/{membership_id}")
def remove_member(profile_id: int, membership_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Remove a user from a profile."""
    raise NotImplementedError("TASK-3.10.02")
