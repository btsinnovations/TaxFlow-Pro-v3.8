"""Profile membership API endpoints for TaxFlow Pro v3.11.02.

Routes:
    GET    /api/profiles                 - list profiles for the current user
    GET    /api/profiles/{id}            - get a single profile (if visible)
    GET    /api/profiles/{id}/members    - list members of a profile
    POST   /api/profiles/{id}/members    - invite/add a user with a role
    PATCH  /api/profiles/{id}/members/{user_id} - change a member's role
    DELETE /api/profiles/{id}/members/{user_id} - remove a member

All routes use the existing ``get_current_user`` JWT dependency.  Profile
visibility is determined by ownership (``clients.user_id``) or explicit
membership in ``profile_memberships``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from .. import models, schemas
from ..local.roles import (
    Membership,
    Role,
    has_role,
    effective_role,
    set_role,
    remove_role,
    list_profile_members,
    list_user_profiles,
)
from ..rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from ..local import settings as local_settings
from ..local.column_encryption import decrypt_for_user
from .auth import get_current_user


router = APIRouter(prefix="/profiles", tags=["profiles"])


def _wrap_tenant(request: Request, db: Session, current_user: models.User):
    """Apply PostgreSQL tenant context when required."""
    if not is_postgres():
        return
    if local_settings.is_single_user():
        set_tenant_id(db, resolve_user_tenant_id(current_user))
        return
    tenant_id = request.headers.get("x-tenant-id")
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
    set_tenant_id(db, int(tenant_id))


def _profile_to_dict(profile: models.Client, user: models.User) -> dict:
    """Serialize a Client profile for API responses."""
    return {
        "id": profile.id,
        "name": profile.name,
        "email": profile.email,
        "tax_id": decrypt_for_user(profile.tax_id, user),
        "user_id": profile.user_id,
        "created_at": profile.created_at,
    }


def _membership_to_dict(membership: Membership) -> dict:
    """Serialize a Membership row using the v3.10 schema shape."""
    return {
        "id": membership.id,
        "user_id": membership.user_id,
        "profile_id": membership.profile_id,
        "role": membership.role,
        "created_at": membership.created_at,
    }


def _require_min_role(db: Session, current_user: models.User, profile_id: int, min_role: str | Role):
    """Raise 403 if the current user lacks at least ``min_role`` on the profile.

    The caller must explicitly request the role they want; owner bypass is NOT
    applied automatically.  This prevents an implicit owner (clients.user_id)
    from accidentally being treated as admin on other profiles."""
    if not has_role(db, current_user.id, profile_id, min_role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient profile role")


@router.get("/", response_model=List[schemas.Client])
def list_profiles(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return all profiles visible to the authenticated user."""
    _wrap_tenant(request, db, current_user)
    profiles = list_user_profiles(db, current_user.id)
    # Apply simple pagination over the in-memory visible list.
    paginated = profiles[skip : skip + limit]
    return [_profile_to_dict(p, current_user) for p in paginated]


@router.get("/{profile_id}", response_model=schemas.Client)
def get_profile(
    request: Request,
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return a single profile if the current user can view it."""
    _wrap_tenant(request, db, current_user)
    _require_min_role(db, current_user, profile_id, Role.viewer)
    profile = db.query(models.Client).filter(models.Client.id == profile_id).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return _profile_to_dict(profile, current_user)


@router.get("/{profile_id}/members", response_model=List[schemas.ProfileMembershipOut])
def list_members(
    request: Request,
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List explicit members of a profile.  Owners are always included implicitly."""
    _wrap_tenant(request, db, current_user)
    _require_min_role(db, current_user, profile_id, Role.viewer)
    members = list_profile_members(db, profile_id)
    return [_membership_to_dict(m) for m in members]


@router.post("/{profile_id}/members", response_model=schemas.ProfileMembershipOut)
def add_member(
    request: Request,
    profile_id: int,
    payload: schemas.ProfileMembershipCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Add a user to a profile with a role.  Requires admin or higher."""
    _wrap_tenant(request, db, current_user)
    _require_min_role(db, current_user, profile_id, Role.admin)

    target_user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    profile = db.query(models.Client).filter(models.Client.id == profile_id).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    # Owner invites require the actor to be an owner.
    if payload.role.lower() == Role.owner.name:
        _require_min_role(db, current_user, profile_id, Role.owner)

    try:
        membership = set_role(
            db,
            user_id=payload.user_id,
            profile_id=profile_id,
            role=payload.role,
            actor_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _membership_to_dict(membership)


@router.patch("/{profile_id}/members/{user_id}", response_model=schemas.ProfileMembershipOut)
def update_member(
    request: Request,
    profile_id: int,
    user_id: int,
    payload: schemas.ProfileMembershipUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Update a member's role on a profile.  Requires admin or higher.

    Promoting to owner requires the actor to be an owner.
    """
    _wrap_tenant(request, db, current_user)
    _require_min_role(db, current_user, profile_id, Role.admin)

    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.role.lower() == Role.owner.name:
        _require_min_role(db, current_user, profile_id, Role.owner)

    try:
        membership = set_role(
            db,
            user_id=user_id,
            profile_id=profile_id,
            role=payload.role,
            actor_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _membership_to_dict(membership)


@router.delete("/{profile_id}/members/{user_id}")
def remove_member(
    request: Request,
    profile_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Remove a member from a profile.  Requires admin or higher.

    Removing an owner requires the actor to be an owner and leaves at least one
    owner behind.
    """
    _wrap_tenant(request, db, current_user)
    _require_min_role(db, current_user, profile_id, Role.admin)

    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Removing an owner requires owner level.
    existing = effective_role(db, user_id, profile_id)
    if existing is not None and existing == Role.owner:
        _require_min_role(db, current_user, profile_id, Role.owner)

    try:
        removed = remove_role(db, user_id=user_id, profile_id=profile_id, actor_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not removed:
        # If the user is the implicit owner, they cannot be removed via membership.
        profile = db.query(models.Client).filter(models.Client.id == profile_id).first()
        if profile is not None and profile.user_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile owner cannot be removed through memberships; transfer ownership first",
            )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    return {"ok": True}
