from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database.db import get_db
from app.middleware.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/users", tags=["Users"])

class ProfileUpdateRequest(BaseModel):
    name: str

class PlanUpdateRequest(BaseModel):
    plan: str

@router.patch("/profile")
async def update_profile(
    request: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user profile full name"""
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.full_name = request.name
    db.commit()
    db.refresh(user)
    
    return {
        "message": "Profile updated successfully",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.full_name,
            "plan": user.plan
        }
    }

@router.patch("/plan")
async def update_plan(
    request: PlanUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user subscription plan"""
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Standardize plan name
    plan_name = request.plan.title()
    if plan_name not in ["Free", "Pro", "Enterprise"]:
        raise HTTPException(status_code=400, detail="Invalid plan name")
        
    user.plan = plan_name
    db.commit()
    db.refresh(user)
    
    return {
        "message": f"Successfully upgraded to {plan_name}",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.full_name,
            "plan": user.plan
        }
    }

