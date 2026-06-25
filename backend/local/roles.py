"""Profile roles and membership helpers for TaxFlow Pro v3.11.02.

Implements the v3.11.02 "Profile Roles & Memberships" module.  Profiles are
represented by the existing :class:`Client` table (a client is a profile in
v3.11).  Each :class:`Membership` row grants a :class:`Role` to a user for a
specific profile.

The role hierarchy is ordered::

    owner > admin > bookkeeper > viewer

Higher roles implicitly satisfy lower-role checks.  Helpers are provided to:

* ``has_role`` — test whether a user has at least the requested role on a
  profile (including ownership through the ``clients.user_id`` owner column).
* ``set_role`` — upsert a membership role, optionally requiring an owner
  level actor so that the last owner cannot be demoted or removed.
* ``require_min_role`` — FastAPI dependency factory for route guards.

All operations are offline-first and rely only on the local SQLAlchemy models.
"""
from __future__ import annotations

import enum
from typing import Optional, Type

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from ..database import Base
from .. import models as _models


class Role(enum.IntEnum):
    """Ordered role levels for profile membership."""

    viewer = 10
    bookkeeper = 20
    admin = 30
    owner = 40


# The canonical ProfileMembership model lives in backend.models so it shares the
# same Base metadata and table definition. This alias keeps the roles module's
# API stable without re-declaring the table (which would conflict at import).
Membership = _models.ProfileMembership


# ---------------------------------------------------------------------------
# Role helpers
# ---------------------------------------------------------------------------


def _role_from_value(value: str | Role) -> Role:
    """Convert a role string or Role enum to a Role enum."""
    if isinstance(value, Role):
        return value
    try:
        return Role[value.lower()]
    except KeyError as exc:
        raise ValueError(f"Invalid role: {value!r}") from exc


def has_role(
    db: Session,
    user_id: int,
    profile_id: int,
    min_role: str | Role,
) -> bool:
    """Return ``True`` if ``user_id`` has at least ``min_role`` on ``profile_id``.

    Ownership always satisfies every role check.
    """
    required = _role_from_value(min_role)
    actual = effective_role(db, user_id, profile_id)
    if actual is None:
        return False
    return actual.value >= required.value


def effective_role(db: Session, user_id: int, profile_id: int) -> Optional[Role]:
    """Return the highest role a user holds on a profile, or ``None``.

    The implicit profile owner (``client.user_id == user_id``) is always
    considered an owner even when no explicit Membership row exists.
    """
    # Implicit ownership from the clients table.
    client = db.query(_models.Client).filter(_models.Client.id == profile_id).first()
    if client is not None and client.user_id == user_id:
        return Role.owner

    membership = (
        db.query(Membership)
        .filter(Membership.user_id == user_id, Membership.profile_id == profile_id)
        .first()
    )
    if membership is None:
        return None
    try:
        return Role[membership.role.lower()]
    except KeyError:
        return None


def set_role(
    db: Session,
    user_id: int,
    profile_id: int,
    role: str | Role,
    actor_user_id: Optional[int] = None,
    allow_owner_demotion: bool = False,
) -> Membership:
    """Set (upsert) the role for ``user_id`` on ``profile_id``.

    Args:
        db: SQLAlchemy session.
        user_id: User whose membership is being modified.
        profile_id: Target profile (client) id.
        role: Desired role string or :class:`Role`.
        actor_user_id: Optional id of the user performing the action.  When
            provided, the actor must be an owner on the profile and the action
            must not leave the profile without an owner.
        allow_owner_demotion: If ``False`` (default), refuse to demote the last
            owner.  This applies when the actor is an owner as well as when
            editing one's own membership.

    Returns:
        The created or updated Membership row.

    Raises:
        ValueError: If the role is invalid or ownership invariants would be
            violated.
    """
    new_role = _role_from_value(role)
    membership = (
        db.query(Membership)
        .filter(Membership.user_id == user_id, Membership.profile_id == profile_id)
        .first()
    )

    # Ownership invariant: if actor is supplied they must be an owner.
    if actor_user_id is not None and not has_role(db, actor_user_id, profile_id, Role.owner):
        raise ValueError("Only profile owners can manage memberships")

    # Refuse to leave profile without an owner when demoting / removing an owner.
    if membership is not None and new_role != Role.owner and not allow_owner_demotion:
        current_role = _role_from_value(membership.role)
        if current_role == Role.owner and _count_owners(db, profile_id) <= 1:
            raise ValueError("Cannot demote the last owner")

    if membership is None:
        membership = Membership(user_id=user_id, profile_id=profile_id, role=new_role.name)
        db.add(membership)
    else:
        membership.role = new_role.name

    db.commit()
    db.refresh(membership)
    return membership


def remove_role(
    db: Session,
    user_id: int,
    profile_id: int,
    actor_user_id: Optional[int] = None,
) -> bool:
    """Remove a user's explicit membership from a profile.

    The implicit profile owner (``clients.user_id``) cannot be removed through
    this function; ownership must be transferred by updating the client row.
    When ``actor_user_id`` is supplied, the actor must be an owner.

    Returns:
        ``True`` if a membership row was deleted, ``False`` if none existed.
    """
    membership = (
        db.query(Membership)
        .filter(Membership.user_id == user_id, Membership.profile_id == profile_id)
        .first()
    )
    if membership is None:
        return False

    if actor_user_id is not None and not has_role(db, actor_user_id, profile_id, Role.owner):
        raise ValueError("Only profile owners can remove members")

    current_role = _role_from_value(membership.role)
    if current_role == Role.owner:
        owner_count = _count_owners(db, profile_id)
        if owner_count <= 1:
            raise ValueError("Cannot remove the last owner")

    db.delete(membership)
    db.commit()
    return True


def _count_owners(db: Session, profile_id: int) -> int:
    """Count distinct owners of a profile.

    The implicit client owner (``clients.user_id``) always counts as one owner.
    Explicit membership rows with role owner count only if they belong to a
    different user than the implicit owner.
    """
    client = db.query(_models.Client).filter(_models.Client.id == profile_id).first()
    implicit_owner_id = client.user_id if client is not None else None

    explicit_owners = (
        db.query(Membership)
        .filter(
            Membership.profile_id == profile_id,
            Membership.role.ilike("owner"),
        )
        .all()
    )

    if implicit_owner_id is None:
        return len(explicit_owners)

    # Count the implicit owner plus any explicit owner rows that do not belong to them.
    return 1 + sum(1 for m in explicit_owners if m.user_id != implicit_owner_id)


def list_profile_members(db: Session, profile_id: int) -> list[Membership]:
    """Return all explicit membership rows for a profile."""
    return db.query(Membership).filter(Membership.profile_id == profile_id).all()


def list_user_profiles(db: Session, user_id: int) -> list[_models.Client]:
    """Return all profiles (clients) visible to a user.

    A profile is visible if the user owns it or has any explicit membership.
    """
    owned_profile_ids = {
        row.id for row in db.query(_models.Client.id).filter(_models.Client.user_id == user_id).all()
    }
    member_profile_ids = {
        row.profile_id
        for row in db.query(Membership.profile_id).filter(Membership.user_id == user_id).all()
    }
    visible_ids = sorted(owned_profile_ids | member_profile_ids)
    if not visible_ids:
        return []
    return db.query(_models.Client).filter(_models.Client.id.in_(visible_ids)).all()


# ---------------------------------------------------------------------------
# FastAPI dependency factory
# ---------------------------------------------------------------------------


def require_min_role(min_role: str | Role):
    """Return a FastAPI dependency that enforces ``min_role`` on a profile.

    The dependency expects ``request`` and ``db`` to be available in the
    route signature.  Example usage::

        @router.patch("/{user_id}")
        def update_member(
            profile_id: int,
            user_id: int,
            request: Request,
            db: Session = Depends(get_db),
            current_user: User = Depends(get_current_user),
            _: None = Depends(require_min_role("admin")),
        ):
            ...

    Because FastAPI dependencies cannot directly access path parameters other
    than through the request, callers typically use the helper functions above
    directly inside route handlers for path-parameterised guards.  This factory
    is retained for simple fixed-scope guards on non-parameterised endpoints.
    """
    from fastapi import HTTPException, Request, Depends
    from sqlalchemy.orm import Session
    from ..database import get_db
    from ..routers.auth import get_current_user as _get_current_user

    required = _role_from_value(min_role)

    def _check(
        request: Request,
        db: Session = Depends(get_db),
        current_user: _models.User = Depends(_get_current_user),
    ) -> None:
        profile_id = request.path_params.get("profile_id") or request.path_params.get("id")
        if profile_id is None:
            raise HTTPException(status_code=400, detail="profile_id path parameter required")
        profile_id = int(profile_id)
        if not has_role(db, current_user.id, profile_id, required):
            raise HTTPException(status_code=403, detail="Insufficient profile role")

    return _check
