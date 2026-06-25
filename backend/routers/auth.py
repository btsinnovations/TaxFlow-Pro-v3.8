"""Auth router for TaxFlow Pro v3.9.

Implements the hybrid local auth model:
- /auth/boot — first boot only; seeds the single local admin.
- /auth/login — accepts OAuth2 form or JSON; verifies master password; returns JWT.
- /auth/register — retained for the existing v3.7 test suite only.
- /auth/me — returns current user decoded from JWT.
- /auth/change-password — updates master password with entropy policy.
"""
from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..rls import is_postgres, set_tenant_id
from ..security.timing_safe import (
    constant_time_compare,
    constant_time_user_lookup,
    constant_time_verify_password,
)
from ..auth import (
    SECRET_KEY,
    authenticate_local_user,
    boot_local_admin,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    is_first_boot,
    logout_local_user,
    register_column_crypto_manager,
    revoke_access_token,
    revoke_refresh_family,
    revoke_refresh_token,
    rotate_refresh_token,
    cleanup_expired_revoked_tokens,
)
from ..auth_rate_limit import (
    check_login_attempt,
    record_login_failure,
    record_login_success,
)
from ..utils.password_policy import validate_master_password
from ..utils.redaction import redact_pii
from ..audit import record, AuditAction, AuditResource

# Backward-compatible re-exports (tests import these from this module)
get_password_hash = hash_password

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


class BootRequest(BaseModel):
    password: str
    keyfile_path: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str
    keyfile_path: str | None = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


def _wrap_tenant(request: Request, db: Session):
    if is_postgres() and request.headers.get("x-tenant-id"):
        try:
            set_tenant_id(db, int(request.headers.get("x-tenant-id")))
        except ValueError:
            pass


def _check_password_policy(password: str, username: str | None = None) -> None:
    failures = validate_master_password(password, username)
    if failures:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Password does not meet security policy", "failures": failures},
        )


# Define _get_current_user early so routes and other modules can reference it.
def _get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    _wrap_tenant(request, db)
    # Fallback to Authorization header if OAuth2 scheme didn't capture (e.g. JSON login stored in header)
    if token is None:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # Server-side session binding enforces expiration and explicit revocation.
    payload = decode_access_token(token, db)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user_id = int(payload.get("sub"))
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def _create_access_session(db: Session, user_id: int) -> str:
    """Issue an access token bound to a server-side Session row."""
    return create_access_token(user_id, db=db)



# Public alias used by other routers.
get_current_user = _get_current_user



def _timing_safe_authenticate(db: Session, username: str, password: str) -> Optional[models.User]:
    """Authenticate the single local user without leaking username timing.

    This is a single-tenant local app: there is exactly one master user. The
    supplied username is accepted for that user (original behavior), but the
    lookup still performs a constant-time username comparison so that the
    processing time does not depend on the supplied username value.
    """
    user = constant_time_user_lookup(db, username)
    # Always run password verification against a real hash. If the database is
    # empty, use a dummy hash so the failure path performs the same bcrypt work.
    target_hash = user.hashed_password if hasattr(user, "hashed_password") else None
    password_ok = constant_time_verify_password(password, target_hash)
    return user if (password_ok and isinstance(user, models.User)) else None

@router.get("/status")
def auth_status(db: Session = Depends(get_db)):
    return {"first_boot": is_first_boot(db)}


@router.post("/boot", response_model=schemas.TokenPair)
def boot(request: Request, body: BootRequest, db: Session = Depends(get_db)):
    _wrap_tenant(request, db)
    if not is_first_boot(db):
        # Uniform failure path: run a dummy password check before returning.
        _timing_safe_authenticate(db, body.password, body.password)
        raise HTTPException(status_code=400, detail="Already initialized")
    policy_failures = _check_password_policy(body.password)
    if policy_failures:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Password does not meet security policy", "failures": policy_failures},
        )
    keyfile_path = Path(body.keyfile_path) if body.keyfile_path else None
    try:
        user = boot_local_admin(db, body.password, keyfile_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    access = _create_access_session(db, user.id)
    refresh = create_refresh_token(db, user.id)
    return {"access_token": access, "token_type": "bearer", "refresh_token": refresh}


@router.post("/register", response_model=schemas.User)
def register(request: Request, user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Registration backdoor — disabled after first boot."""
    _wrap_tenant(request, db)
    if not is_first_boot(db):
        raise HTTPException(
            status_code=403,
            detail="Registration is disabled after initial setup. Use /auth/boot.",
        )
    _check_password_policy(user.password, user.username)
    existing = db.query(models.User).filter(models.User.username == user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
    import base64, secrets
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hash_password(user.password),
        is_active=True,
        encryption_salt=base64.b64encode(secrets.token_bytes(16)).decode("ascii"),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/login", response_model=schemas.TokenPair)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    _wrap_tenant(request, db)
    check_login_attempt(form_data.username)
    user = _timing_safe_authenticate(db, form_data.username, form_data.password)
    if user is None:
        record_login_failure(form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect master password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.keyfile_path:
        record_login_failure(form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Keyfile required; use /auth/login-json",
            headers={"WWW-Authenticate": "Bearer"},
        )
    record_login_success(form_data.username)
    register_column_crypto_manager(
        user.id, form_data.password, user.encryption_salt
    )
    access = _create_access_session(db, user.id)
    refresh = create_refresh_token(db, user.id)
    return {"access_token": access, "token_type": "bearer", "refresh_token": refresh}


@router.post("/login-json", response_model=schemas.TokenPair)
def login_json(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    _wrap_tenant(request, db)
    check_login_attempt(body.username)
    keyfile_path = Path(body.keyfile_path) if body.keyfile_path else None
    try:
        user = authenticate_local_user(db, body.password, keyfile_path)
    except ValueError as exc:
        record_login_failure(body.username)
        raise HTTPException(status_code=401, detail=str(exc))
    if user is None:
        record_login_failure(body.username)
        raise HTTPException(status_code=401, detail="Incorrect master password")
    record_login_success(body.username)
    access = _create_access_session(db, user.id)
    refresh = create_refresh_token(db, user.id)
    return {"access_token": access, "token_type": "bearer", "refresh_token": refresh}


@router.post("/refresh", response_model=schemas.TokenPair)
def refresh_token(request: Request, body: schemas.RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a rotated access + refresh token pair."""
    _wrap_tenant(request, db)
    new_refresh, access_payload = rotate_refresh_token(db, body.refresh_token)
    if access_payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    access = _create_access_session(db, int(access_payload.get("sub")))
    return {"access_token": access, "token_type": "bearer", "refresh_token": new_refresh}


@router.post("/change-password")
def change_password(
    request: Request,
    body: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db)
    if not constant_time_verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")
    _check_password_policy(body.new_password, current_user.username)
    current_user.hashed_password = hash_password(body.new_password)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    record(
        db,
        current_user,
        AuditAction.UPDATE,
        AuditResource.USER,
        resource_id=current_user.id,
        details={"event": "password_changed"},
    )
    return {"ok": True}


@router.get("/me", response_model=schemas.User)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/logout")
def logout(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    refresh_token: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db)
    # Fallback to Authorization header if OAuth2 scheme didn't capture the token.
    if token is None:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]
    if token:
        revoke_access_token(db, token)
    if refresh_token:
        # Revoke the whole refresh family on explicit logout.
        revoke_refresh_family(db, refresh_token)
    # Clear the in-memory column-encryption manager so plaintext cannot be read
    # after the user explicitly ends their session.
    logout_local_user(db, current_user)
    return {"ok": True}
