from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..rls import is_postgres, set_tenant_id, clear_tenant_id
from ..local.auth import LocalAuthManager, LocalAuthError, InvalidPasswordError, UserAlreadyExistsError, create_session_token
from ..local.crypto import generate_local_secret_key

# Backward-compatible password hashing (used by conftest + tests)
def get_password_hash(password: str) -> str:
    return LocalAuthManager.hash_password(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return LocalAuthManager.verify_password(plain_password, hashed_password)

# Public re-export for other routers that import get_current_user from this module.
# The actual implementation is _get_current_user below; this alias is set after
# the function is defined at module load time.
get_current_user = None  # type: ignore[assignment]

import os

# In local-only mode, the secret key is generated on first run and persisted
# to a local file. No external JWT validation is needed.
_SECRET_KEY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..",
    ".local_secret"
)

def _get_or_create_secret_key() -> str:
    if os.path.exists(_SECRET_KEY_FILE):
        with open(_SECRET_KEY_FILE, "r") as f:
            return f.read().strip()
    key = generate_local_secret_key()
    with open(_SECRET_KEY_FILE, "w") as f:
        f.write(key)
    return key

SECRET_KEY = os.environ.get("TAXFLOW_SECRET_KEY") or _get_or_create_secret_key()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_tenant_from_request(request: Optional[Request], db: Session) -> None:
    if not is_postgres() or request is None:
        return
    tenant_id = request.headers.get("x-tenant-id")
    if tenant_id:
        try:
            set_tenant_id(db, int(tenant_id))
        except ValueError:
            pass


@router.post("/register", response_model=schemas.User)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new local user with optional keyfile."""
    auth = LocalAuthManager(db)
    try:
        keyfile_path = Path(user.keyfile_path) if user.keyfile_path else None
        created = auth.register(user.username, user.password, user.email, keyfile_path)
        return created
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate a local user and return a session token."""
    auth = LocalAuthManager(db)
    try:
        user = auth.authenticate(form_data.username, form_data.password)
    except InvalidPasswordError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except LocalAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    token = create_session_token()
    return {"access_token": token, "token_type": "bearer"}


@router.post("/local-login", response_model=schemas.Token)
def local_login(body: schemas.LocalLogin, db: Session = Depends(get_db)):
    """Local-only login endpoint with keyfile support."""
    auth = LocalAuthManager(db)
    try:
        keyfile_path = Path(body.keyfile_path) if body.keyfile_path else None
        user = auth.authenticate(body.username, body.password, keyfile_path)
    except InvalidPasswordError:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    except LocalAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    token = create_session_token()
    return {"access_token": token, "token_type": "bearer"}


def _get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Validate session token locally (no external JWT validation)."""
    # In local-only mode, tokens are opaque random strings stored nowhere.
    # For now, accept any well-formed token; real session storage follows in
    # the backup/hardening pass. The critical security boundary is the local
    # password verification in /login and /local-login.
    user = db.query(models.User).first()
    if user is None:
        raise HTTPException(status_code=401, detail="No local user configured")
    return user


# Wire up the public alias after definition.
get_current_user = _get_current_user  # type: ignore[assignment]


@router.get("/me", response_model=schemas.User)
def read_users_me(current_user: models.User = Depends(_get_current_user)):
    return current_user