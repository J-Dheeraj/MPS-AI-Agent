"""
MPS Server - Authentication and RBAC
JWT tokens, bcrypt password hashing, lockout after 5 failures
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .database import User, get_db

SECRET_KEY  = "CHANGE_THIS_IN_PRODUCTION_USE_SECRETS_COMMAND"
ALGORITHM   = "HS256"
TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

ROLES = {"volunteer", "vetter", "admin"}

# ── Password ──────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# ── Token ─────────────────────────────────────

def create_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "jti": str(uuid.uuid4())})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

# ── Login / lockout ───────────────────────────

def authenticate_user(db: Session, username: str, password: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check lockout
    if user.locked_until and datetime.now(timezone.utc) < user.locked_until.replace(tzinfo=timezone.utc):
        remaining = (user.locked_until.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).seconds // 60
        raise HTTPException(status_code=403, detail=f"Account locked. Try again in {remaining} minutes.")

    if not verify_password(password, user.hashed_pw):
        user.failed_logins += 1
        if user.failed_logins >= 5:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
            db.commit()
            raise HTTPException(status_code=403, detail="Account locked for 30 minutes after 5 failed attempts.")
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Success — reset failure count
    user.failed_logins = 0
    user.locked_until = None
    db.commit()
    return user

# ── Current user dependency ───────────────────

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(token)
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user

def require_role(*roles: str):
    """Dependency factory — require one of the given roles."""
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{current_user.role}' cannot access this endpoint"
            )
        return current_user
    return checker

require_volunteer = require_role("volunteer", "vetter", "admin")
require_vetter    = require_role("vetter", "admin")
require_admin     = require_role("admin")
