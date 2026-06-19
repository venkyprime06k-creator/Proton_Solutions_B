from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import jwt
from pydantic import BaseModel, EmailStr
from typing import Optional
import hashlib
import hmac
import os
import uuid

from app.config.settings import settings
from app.database.db import get_db
from app.models.user import User, Session as UserSession
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

def hash_password(password: str) -> str:
    """Hash password securely using PBKDF2-SHA256"""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"{salt.hex()}:{key.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against its hash"""
    try:
        salt_hex, key_hex = hashed.split(':')
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        actual_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return hmac.compare_digest(actual_key, expected_key)
    except Exception:
        return False

# Request schemas
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str

# Response schemas
class UserInfo(BaseModel):
    id: str
    email: str
    name: str
    plan: str

class AuthResponse(BaseModel):
    token: str
    user: UserInfo

def create_token(user_id: str) -> str:
    """Create JWT token"""
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expiry_minutes)
    payload = {
        "sub": user_id,
        "exp": expire
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

@router.post("/signup", response_model=AuthResponse)
async def signup(
    data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """Register new user"""
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    hashed = hash_password(data.password)
    user = User(
        id=str(uuid.uuid4()),
        email=data.email,
        password_hash=hashed,
        full_name=data.name,
        plan="Free"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    token = create_token(user.id)
    session = UserSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.jwt_expiry_minutes)
    )
    db.add(session)
    db.commit()
    
    return AuthResponse(
        token=token,
        user=UserInfo(
            id=user.id,
            email=user.email,
            name=user.full_name or "",
            plan=user.plan or "Free"
        )
    )

# Alias for signup
@router.post("/register", response_model=AuthResponse)
async def register(data: RegisterRequest, db: Session = Depends(get_db)):
    return await signup(data, db)

@router.post("/signin", response_model=AuthResponse)
async def signin(
    data: LoginRequest,
    db: Session = Depends(get_db)
):
    """Login user"""
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    token = create_token(user.id)
    session = UserSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.jwt_expiry_minutes)
    )
    db.add(session)
    db.commit()
    
    return AuthResponse(
        token=token,
        user=UserInfo(
            id=user.id,
            email=user.email,
            name=user.full_name or "",
            plan=user.plan or "Free"
        )
    )

# Alias for signin
@router.post("/login", response_model=AuthResponse)
async def login(data: LoginRequest, db: Session = Depends(get_db)):
    return await signin(data, db)

@router.post("/signout")
async def signout(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Sign out user - delete user sessions"""
    db.query(UserSession).filter(UserSession.user_id == current_user["id"]).delete()
    db.commit()
    return {"message": "Logged out successfully"}

# Alias for signout
@router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return await signout(current_user, db)

@router.get("/me", response_model=UserInfo)
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user details"""
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserInfo(
        id=user.id,
        email=user.email,
        name=user.full_name or "",
        plan=user.plan or "Free"
    )

@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change password"""
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not verify_password(data.currentPassword, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
        
    user.password_hash = hash_password(data.newPassword)
    db.commit()
    return {"message": "Password changed successfully"}