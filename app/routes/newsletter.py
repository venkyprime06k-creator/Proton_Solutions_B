from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.database.db import get_db
from app.models.newsletter import NewsletterSubscriber

router = APIRouter(prefix="/newsletter", tags=["Newsletter"])

class SubscribeRequest(BaseModel):
    email: EmailStr

@router.post("/subscribe")
async def subscribe(
    data: SubscribeRequest,
    db: Session = Depends(get_db)
):
    """Subscribe to newsletter"""
    
    # Check if already subscribed
    existing = db.query(NewsletterSubscriber).filter(
        NewsletterSubscriber.email == data.email
    ).first()
    
    if existing:
        if existing.is_active:
            return {"message": "Already subscribed"}
        else:
            # Reactivate
            existing.is_active = True
            db.commit()
            return {"message": "Re-subscribed successfully"}
    
    # Create new subscriber
    subscriber = NewsletterSubscriber(
        email=data.email
    )
    db.add(subscriber)
    db.commit()
    
    return {"message": "Subscribed successfully"}

@router.post("/unsubscribe")
async def unsubscribe(
    data: SubscribeRequest,
    db: Session = Depends(get_db)
):
    """Unsubscribe from newsletter"""
    
    subscriber = db.query(NewsletterSubscriber).filter(
        NewsletterSubscriber.email == data.email
    ).first()
    
    if subscriber:
        subscriber.is_active = False
        db.commit()
    
    return {"message": "Unsubscribed successfully"}