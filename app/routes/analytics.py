from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.middleware.auth import get_current_user
from app.models.user import User, Conversation

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/usage")
async def get_usage(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user usage statistics"""
    user = db.query(User).filter(User.id == current_user["id"]).first()
    
    # Count conversations
    conversation_count = db.query(Conversation).filter(
        Conversation.user_id == current_user["id"]
    ).count()
    
    # Calculate account age
    days = 0
    if user and user.created_at:
        try:
            # Safely calculate difference
            import datetime
            delta = datetime.datetime.now(user.created_at.tzinfo) - user.created_at
            days = delta.days
        except Exception:
            days = 0
            
    return {
        "total_requests": user.total_requests if user else 0,
        "total_tokens": user.total_tokens if user else 0,
        "conversation_count": conversation_count,
        "account_age_days": days
    }

@router.get("/metrics")
async def get_metrics(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get usage metrics in dashboard-friendly format"""
    user = db.query(User).filter(User.id == current_user["id"]).first()
    total_calls = user.total_requests if user else 0
    
    # Determine limit based on plan
    limit = 100
    if user:
        user_plan = (user.plan or "Free").lower()
        if user_plan == "pro":
            limit = 10000
        elif user_plan == "enterprise":
            limit = 100000
            
    return {
        "metrics": {
            "totalCalls": total_calls,
            "limit": limit,
            "successfulCalls": total_calls,
            "failedCalls": 0,
            "averageResponseTime": 320
        }
    }