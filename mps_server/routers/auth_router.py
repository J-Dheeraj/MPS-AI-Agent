from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from ..database import User, get_db
from ..auth import authenticate_user, create_token, hash_password, get_current_user, TOKEN_EXPIRE_MINUTES
from ..services.audit import log_event
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    username:  str
    password:  str
    full_name: str
    role:      str  # volunteer / vetter / admin

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str
    role:         str
    full_name:    str
    user_id:      str

@router.post("/login", response_model=TokenResponse)
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, form.username, form.password)
    token = create_token(
        {"sub": user.id, "role": user.role},
        expires_delta=timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    )
    log_event(db, "login", user_id=user.id, role=user.role,
              client_ip=request.client.host if request.client else None)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        full_name=user.full_name,
        user_id=user.id,
    )

@router.post("/logout")
def logout(request: Request, current_user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    log_event(db, "logout", user_id=current_user.id, role=current_user.role,
              client_ip=request.client.host if request.client else None)
    return {"message": "Logged out"}

@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Admin use only — create new user accounts."""
    if req.role not in ("volunteer", "vetter", "admin"):
        raise HTTPException(400, "Invalid role")
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(400, "Username already exists")
    user = User(
        username=req.username,
        hashed_pw=hash_password(req.password),
        full_name=req.full_name,
        role=req.role,
    )
    db.add(user)
    db.commit()
    return {"user_id": user.id, "username": user.username, "role": user.role}
