from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import bcrypt
from ..database import get_db
from .. import models, schemas
from ..rls import is_postgres, set_tenant_id, clear_tenant_id

import os

SECRET_KEY = os.environ.get(
    "TAXFLOW_SECRET_KEY",
    "taxflow-dev-secret-key-change-in-production-2026"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

router = APIRouter(prefix="/auth", tags=["auth"])

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


async def get_current_user_optional(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)),
):
    """Return the current user if authenticated, None otherwise."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    user = db.query(models.User).filter(models.User.username == username).first()
    return user

def _set_tenant_from_request(request: Optional[Request], db: Session) -> None:
    """Set RLS tenant context when X-Tenant-ID header is present on PostgreSQL."""
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
    try:
        if db.query(models.User).filter(models.User.username == user.username).first():
            raise HTTPException(status_code=400, detail="Username already registered")
        if db.query(models.User).filter(models.User.email == user.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        db_user = models.User(
            username=user.username,
            email=user.email,
            hashed_password=get_password_hash(user.password)
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@router.post("/login", response_model=schemas.TokenWithUser)
async def login(request: Request, db: Session = Depends(get_db)):
    """Authenticate with either JSON or form-encoded credentials."""
    content_type = request.headers.get("content-type", "")
    try:
        if "application/json" in content_type:
            body = await request.json()
            username = body.get("username")
            password = body.get("password")
        else:
            form = await request.form()
            username = form.get("username")
            password = form.get("password")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unable to parse login credentials",
        )

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username and password are required",
        )

    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer", "user": user}

@router.post("/logout")
def logout():
    """JWT logout is client-side; inform the client the token should be discarded."""
    return {"detail": "Logged out successfully"}

@router.get("/me", response_model=schemas.User)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user
