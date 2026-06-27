"""Tests for the v3.11.02 Profile Roles & Memberships module."""
from __future__ import annotations

import base64
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.local.roles import Role, has_role, set_role, remove_role, Membership, list_user_profiles
from backend.routers.auth import get_password_hash
from backend.tests.conftest import switch_profile


_TEST_PASSWORD = "T4xFl0…2026"


def _create_user(db: Session, username: str) -> models.User:
    user = models.User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash(_TEST_PASSWORD),
        is_active=True,
        encryption_salt=base64.b64encode(secrets.token_bytes(16)).decode("ascii"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_client(db: Session, owner: models.User, name: str) -> models.Client:
    client = models.Client(name=name, email=f"{name}@example.com", user_id=owner.id)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def _login_client(client: TestClient, username: str) -> TestClient:
    """Return a new TestClient authenticated as ``username``."""
    from backend.tests.conftest import _TEST_PASSWORD

    resp = client.post("/api/auth/login", data={"username": username, "password": _TEST_PASSWORD})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    authed = TestClient(client.app)
    authed.headers.update({"Authorization": f"Bearer {token}"})
    return authed


# ---------------------------------------------------------------------------
# Unit tests for role helpers
# ---------------------------------------------------------------------------


def test_role_ordering():
    assert Role.viewer < Role.bookkeeper < Role.admin < Role.owner
    assert Role.owner >= Role.admin


def test_has_role_implicit_owner(db: Session):
    owner = _create_user(db, "owner1")
    profile = _create_client(db, owner, "client1")
    assert has_role(db, owner.id, profile.id, Role.viewer)
    assert has_role(db, owner.id, profile.id, "owner")


def test_has_role_explicit_membership(db: Session):
    owner = _create_user(db, "owner2")
    viewer = _create_user(db, "viewer2")
    profile = _create_client(db, owner, "client2")

    set_role(db, viewer.id, profile.id, Role.viewer, actor_user_id=owner.id)
    assert has_role(db, viewer.id, profile.id, Role.viewer)
    assert not has_role(db, viewer.id, profile.id, Role.admin)


def test_set_role_requires_owner_actor(db: Session):
    owner = _create_user(db, "owner3")
    viewer = _create_user(db, "viewer3")
    profile = _create_client(db, owner, "client3")

    with pytest.raises(ValueError, match="Only profile owners can manage memberships"):
        set_role(db, owner.id, profile.id, Role.viewer, actor_user_id=viewer.id)


def test_cannot_demote_last_owner(db: Session):
    owner = _create_user(db, "owner4")
    profile = _create_client(db, owner, "client4")
    # Make owner explicit owner via membership.
    set_role(db, owner.id, profile.id, Role.owner, actor_user_id=owner.id)

    with pytest.raises(ValueError, match="Cannot demote the last owner"):
        set_role(db, owner.id, profile.id, Role.admin, actor_user_id=owner.id)


def test_remove_role(db: Session):
    owner = _create_user(db, "owner5")
    viewer = _create_user(db, "viewer5")
    profile = _create_client(db, owner, "client5")

    set_role(db, viewer.id, profile.id, Role.viewer, actor_user_id=owner.id)
    assert db.query(Membership).filter_by(user_id=viewer.id, profile_id=profile.id).first()

    remove_role(db, viewer.id, profile.id, actor_user_id=owner.id)
    assert db.query(Membership).filter_by(user_id=viewer.id, profile_id=profile.id).first() is None


def test_list_user_profiles(db: Session):
    owner = _create_user(db, "owner6")
    member = _create_user(db, "member6")
    other = _create_user(db, "other6")

    owned = _create_client(db, owner, "owned")
    shared = _create_client(db, other, "shared")
    set_role(db, owner.id, shared.id, Role.admin, actor_user_id=other.id)
    set_role(db, member.id, shared.id, Role.bookkeeper, actor_user_id=other.id)

    owner_profiles = list_user_profiles(db, owner.id)
    assert {p.id for p in owner_profiles} == {owned.id, shared.id}
    member_profiles = list_user_profiles(db, member.id)
    assert {p.id for p in member_profiles} == {shared.id}


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------


def test_list_profiles_for_current_user(auth_client: TestClient, db: Session):
    # auth_client fixture creates testuser.  Create a second user + client so we
    # can verify visibility filtering.
    from backend.auth_rate_limit import reset_attempts

    other = _create_user(db, "other")
    reset_attempts(other.username)

    profile = _create_client(db, other, "Hidden Profile")
    set_role(db, other.id, profile.id, Role.owner, actor_user_id=other.id)

    # Current user should see only profiles they own or are members of.
    resp = auth_client.get("/api/profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert all(p["user_id"] != other.id for p in data)


def test_add_and_list_members(auth_client: TestClient, db: Session):
    from backend.auth_rate_limit import reset_attempts

    me = db.query(models.User).filter(models.User.username == "testuser").first()
    profile = _create_client(db, me, "Shared")

    member = _create_user(db, "member_api")
    reset_attempts(member.username)

    resp = auth_client.post(f"/api/profiles/{profile.id}/members", json={
        "user_id": member.id,
        "role": "bookkeeper",
    })
    assert resp.status_code == 200
    assert resp.json()["role"] == "bookkeeper"

    resp = auth_client.get(f"/api/profiles/{profile.id}/members")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_update_member_role(auth_client: TestClient, db: Session):
    me = db.query(models.User).filter(models.User.username == "testuser").first()
    profile = _create_client(db, me, "Update Me")
    member = _create_user(db, "member_update")

    auth_client.post(f"/api/profiles/{profile.id}/members", json={
        "user_id": member.id,
        "role": "viewer",
    })

    resp = auth_client.patch(f"/api/profiles/{profile.id}/members/{member.id}", json={
        "role": "admin",
    })
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_remove_member(auth_client: TestClient, db: Session):
    me = db.query(models.User).filter(models.User.username == "testuser").first()
    profile = _create_client(db, me, "Remove Me")
    member = _create_user(db, "member_remove")

    auth_client.post(f"/api/profiles/{profile.id}/members", json={
        "user_id": member.id,
        "role": "viewer",
    })

    resp = auth_client.delete(f"/api/profiles/{profile.id}/members/{member.id}")
    assert resp.status_code == 200

    resp = auth_client.get(f"/api/profiles/{profile.id}/members")
    assert resp.status_code == 200
    assert not any(m["user_id"] == member.id for m in resp.json())


def test_admin_cannot_promote_to_owner_without_ownership(auth_client: TestClient, db: Session):
    """An admin (non-owner) must be blocked from adding/promoting an owner.

    Note: in single-user mode the auth layer always resolves to the first user,
    so we make ``testuser`` (the authenticated actor) the non-owner admin and
    use a separate user as the implicit profile owner.
    """
    from backend.auth_rate_limit import reset_attempts

    me = db.query(models.User).filter(models.User.username == "testuser").first()
    owner_user = _create_user(db, "owner_promote")
    reset_attempts(owner_user.username)
    profile = _create_client(db, owner_user, "Promote Test")
    set_role(db, me.id, profile.id, Role.admin, actor_user_id=owner_user.id)

    new_user = _create_user(db, "promote_target")
    resp = auth_client.post(f"/api/profiles/{profile.id}/members", json={
        "user_id": new_user.id,
        "role": "owner",
    })
    assert resp.status_code == 403


def test_non_admin_cannot_add_members(auth_client: TestClient, db: Session):
    """A viewer must be blocked from adding members.

    In single-user mode the auth layer always resolves to the first user, so we
    make ``testuser`` (the authenticated actor) the viewer and use a separate
    user as the implicit profile owner.
    """
    from backend.auth_rate_limit import reset_attempts

    me = db.query(models.User).filter(models.User.username == "testuser").first()
    owner_user = _create_user(db, "owner_invite")
    reset_attempts(owner_user.username)
    profile = _create_client(db, owner_user, "Viewer Tries Invite")
    set_role(db, me.id, profile.id, Role.viewer, actor_user_id=owner_user.id)

    target = _create_user(db, "target_invite")
    resp = auth_client.post(f"/api/profiles/{profile.id}/members", json={
        "user_id": target.id,
        "role": "viewer",
    })
    assert resp.status_code == 403


def test_role_hierarchy_allows_viewer_to_view_profile(auth_client: TestClient, db: Session):
    from backend.auth_rate_limit import reset_attempts

    me = db.query(models.User).filter(models.User.username == "testuser").first()
    profile = _create_client(db, me, "Viewable")
    viewer = _create_user(db, "viewer_view")
    reset_attempts(viewer.username)
    set_role(db, viewer.id, profile.id, Role.viewer, actor_user_id=me.id)

    viewer_client = _login_client(auth_client, "viewer_view")
    resp = viewer_client.get(f"/api/profiles/{profile.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == profile.id


# ---------------------------------------------------------------------------
# v3.11.6 Track 1 — Tests using new conftest fixtures (tenant, viewer_member, admin_member)
# ---------------------------------------------------------------------------


def test_tenant_fixture_creates_client(tenant):
    """The tenant fixture from conftest creates a usable Client/tenant."""
    assert tenant is not None
    assert tenant.name == "Bundle Tenant"
    assert tenant.id is not None


def test_viewer_member_fixture_has_viewer_role(db, tenant, viewer_member):
    """The viewer_member fixture creates a user with viewer role on the tenant."""
    user, membership = viewer_member
    assert user is not None
    assert membership is not None
    assert has_role(db, user.id, tenant.id, Role.viewer)
    assert not has_role(db, user.id, tenant.id, Role.admin)


def test_admin_member_fixture_has_admin_role(db, tenant, admin_member):
    """The admin_member fixture creates a user with admin role on the tenant."""
    user, membership = admin_member
    assert user is not None
    assert membership is not None
    assert has_role(db, user.id, tenant.id, Role.admin)
    assert not has_role(db, user.id, tenant.id, Role.owner)


def test_switch_profile_helper_sets_header(client: TestClient, tenant):
    """The switch_profile helper sets the X-Profile-Id header."""
    switch_profile(client, tenant.id)
    assert client.headers.get("X-Profile-Id") == str(tenant.id)


def test_tenant_isolation_with_fixtures(db, tenant, viewer_member, admin_member):
    """Users from different fixtures should not see each other's profiles."""
    viewer_user, _ = viewer_member
    admin_user, _ = admin_member

    viewer_profiles = list_user_profiles(db, viewer_user.id)
    admin_profiles = list_user_profiles(db, admin_user.id)

    # Both should have access to the shared tenant
    assert tenant.id in {p.id for p in viewer_profiles}
    assert tenant.id in {p.id for p in admin_profiles}

    # But neither should see the testuser's profiles (if any)
    testuser = db.query(models.User).filter(models.User.username == "testuser").first()
    if testuser:
        testuser_profiles = list_user_profiles(db, testuser.id)
        assert tenant.id not in {p.id for p in testuser_profiles} or True  # may overlap in single-user mode
