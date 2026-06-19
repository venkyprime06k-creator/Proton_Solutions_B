from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, AsyncGenerator
import json
from datetime import datetime
import uuid

from app.services.ai_service import ai_service
from app.middleware.auth import get_current_user
from app.database.db import get_db, SessionLocal
from app.models.user import Conversation, User, Message as DBMessage

router = APIRouter(prefix="/chat", tags=["Chat"])

# Request/Response schemas
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    id: str
    content: str
    model: str
    provider: str
    usage: dict

class CreateConversationRequest(BaseModel):
    title: str
    model: str

class MessageRequest(BaseModel):
    conversationId: str
    content: str
    model: Optional[str] = None

@router.get("/conversations")
async def get_conversations(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0
):
    """Get user's conversation list"""
    conversations = db.query(Conversation).filter(
        Conversation.user_id == current_user["id"]
    ).order_by(Conversation.updated_at.desc()).limit(limit).offset(offset).all()
    
    if not conversations:
        return []
        
    conv_ids = [c.id for c in conversations]
    # Query message counts using group_by to avoid N+1 queries
    counts = db.query(
        DBMessage.conversation_id,
        func.count(DBMessage.id).label("count")
    ).filter(
        DBMessage.conversation_id.in_(conv_ids)
    ).group_by(DBMessage.conversation_id).all()
    
    count_map = {r.conversation_id: r.count for r in counts}
    
    return [
        {
            "id": c.id,
            "title": c.title,
            "model": c.model,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "message_count": count_map.get(c.id, 0)
        }
        for c in conversations
    ]

@router.post("/conversations")
async def create_conversation(
    request: CreateConversationRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new conversation"""
    conversation = Conversation(
        id=str(uuid.uuid4()),
        user_id=current_user["id"],
        title=request.title,
        model=request.model,
        messages="[]"
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    return {
        "id": conversation.id,
        "title": conversation.title,
        "model": conversation.model,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at
    }

@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a single conversation and its messages"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user["id"]
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    # Fetch messages from the normalized database table
    db_messages = db.query(DBMessage).filter(
        DBMessage.conversation_id == conversation_id
    ).order_by(DBMessage.created_at.asc()).all()
    
    messages = [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "createdAt": m.created_at.isoformat() if m.created_at else None
        }
        for m in db_messages
    ]
    
    return {
        "conversation": {
            "id": conversation.id,
            "title": conversation.title,
            "model": conversation.model,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at
        },
        "messages": messages
    }

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a conversation"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user["id"]
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    db.delete(conversation)
    db.commit()
    return {"message": "Conversation deleted successfully"}

@router.post("/messages")
async def send_message(
    request: MessageRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send message and get streaming response from AI"""
    conversation = db.query(Conversation).filter(
        Conversation.id == request.conversationId,
        Conversation.user_id == current_user["id"]
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Enforce API usage limits based on subscription plan
    limit = 100
    user_plan = (user.plan or "Free").lower()
    if user_plan == "pro":
        limit = 10000
    elif user_plan == "enterprise":
        limit = 100000
        
    if user.total_requests >= limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Monthly API call limit reached. Please upgrade your plan in the Billing section."
        )
        
    # Construct custom keys dictionary from user preferences
    custom_keys = {
        "openai": user.openai_key,
        "anthropic": user.anthropic_key,
        "gemini": user.gemini_key,
        "groq": user.groq_key,
        "huggingface": user.huggingface_key
    }
        
    # Determine provider/model
    provider = "openrouter"
    ai_model = "openrouter/free"
    
    req_model = request.model or conversation.model
    if req_model:
        req_model_lower = req_model.lower()
        if "basic" in req_model_lower:
            # Basic model tier
            provider = "groq"
            ai_model = "llama-3.1-8b-instant"
        elif "pro" in req_model_lower or "medium" in req_model_lower:
            # Pro model tier
            provider = "openrouter"
            ai_model = "openrouter/free"
        elif "advanced" in req_model_lower or "high" in req_model_lower:
            # Advanced model tier: Use OpenAI/Anthropic/Gemini if custom key is present, otherwise fallback
            if user.openai_key:
                provider = "openai"
                ai_model = "gpt-4o-mini"
            elif user.anthropic_key:
                provider = "anthropic"
                ai_model = "claude-3-5-haiku-20241022"
            elif user.gemini_key:
                provider = "gemini"
                ai_model = "gemini-1.5-flash"
            else:
                provider = "openrouter"
                ai_model = "openrouter/free"
        elif "enterprise" in req_model_lower:
            # Enterprise model tier
            if user.anthropic_key:
                provider = "anthropic"
                ai_model = "claude-3-5-sonnet-20241022"
            elif user.openai_key:
                provider = "openai"
                ai_model = "gpt-4o"
            else:
                provider = "openrouter"
                ai_model = "openrouter/free"
        elif "uncensored" in req_model_lower:
            # Uncensored model tier
            provider = "openrouter"
            ai_model = "openrouter/free"
            
    # Load past messages from database
    db_messages = db.query(DBMessage).filter(
        DBMessage.conversation_id == request.conversationId
    ).order_by(DBMessage.created_at.asc()).all()
    
    messages_to_ai = []
    for msg in db_messages:
        messages_to_ai.append({"role": msg.role, "content": msg.content})
        
    # Append the new user message
    messages_to_ai.append({"role": "user", "content": request.content})
    
    async def generate() -> AsyncGenerator[str, None]:
        assistant_content = ""
        # Create a new standalone DB session to prevent closed session errors in the background generator task
        db_session = SessionLocal()
        try:
            # Get stream from AI service
            async for chunk in ai_service.stream_completion(
                messages=messages_to_ai,
                provider=provider,
                model=ai_model,
                custom_keys=custom_keys
            ):
                assistant_content += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                
            # Stream completed successfully. Now save everything to the database.
            db_conv = db_session.query(Conversation).filter(
                Conversation.id == request.conversationId
            ).first()
            if not db_conv:
                raise Exception("Conversation not found during save")
                
            assistant_msg_id = str(uuid.uuid4())
            db_user_msg = DBMessage(
                id=str(uuid.uuid4()),
                conversation_id=db_conv.id,
                role="user",
                content=request.content,
                created_at=datetime.utcnow()
            )
            db_assistant_msg = DBMessage(
                id=assistant_msg_id,
                conversation_id=db_conv.id,
                role="assistant",
                content=assistant_content,
                created_at=datetime.utcnow()
            )
            db_session.add(db_user_msg)
            db_session.add(db_assistant_msg)
            
            db_conv.updated_at = datetime.utcnow()
            
            # Update user stats
            user_stats = db_session.query(User).filter(User.id == current_user["id"]).first()
            if user_stats:
                user_stats.total_requests += 1
                user_stats.total_tokens += len(request.content.split()) + len(assistant_content.split())
                
            db_session.commit()
            
            # Send completion details to the frontend
            yield f"data: {json.dumps({
                'done': True, 
                'conversationId': db_conv.id, 
                'title': db_conv.title, 
                'messageId': assistant_msg_id
            })}\n\n"
            
        except Exception as e:
            db_session.rollback()
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            db_session.close()
            
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )