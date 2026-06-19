from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database.db import get_db
from app.middleware.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/settings", tags=["Settings"])

class ApiKeysSaveRequest(BaseModel):
    openai: Optional[str] = None
    anthropic: Optional[str] = None
    gemini: Optional[str] = None
    groq: Optional[str] = None
    huggingface: Optional[str] = None

@router.get("/keys-status")
async def get_keys_status(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if custom API keys are configured"""
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {
        "openai": bool(user.openai_key),
        "anthropic": bool(user.anthropic_key),
        "gemini": bool(user.gemini_key),
        "groq": bool(user.groq_key),
        "huggingface": bool(user.huggingface_key)
    }

@router.post("/api-keys")
async def save_api_keys(
    request: ApiKeysSaveRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save custom API keys"""
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if request.openai is not None:
        user.openai_key = request.openai
    if request.anthropic is not None:
        user.anthropic_key = request.anthropic
    if request.gemini is not None:
        user.gemini_key = request.gemini
    if request.groq is not None:
        user.groq_key = request.groq
    if request.huggingface is not None:
        user.huggingface_key = request.huggingface
        
    db.commit()
    return {"message": "API keys updated successfully"}

@router.delete("/api-keys")
async def delete_api_keys(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear all custom API keys"""
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.openai_key = None
    user.anthropic_key = None
    user.gemini_key = None
    user.groq_key = None
    user.huggingface_key = None
    
    db.commit()
    return {"message": "All API keys cleared"}
