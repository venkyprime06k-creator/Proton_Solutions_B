from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time
import logging

from app.config.settings import settings
from app.routes import auth, chat, analytics, newsletter, users, settings as settings_route
from app.database.db import engine, Base
# Import all models to ensure they are registered with Base.metadata
from app.models.user import User, Session, Conversation, Message
from app.models.newsletter import NewsletterSubscriber

# Auto-create tables on startup
Base.metadata.create_all(bind=engine)

# Startup migration for legacy messages to Message table
def migrate_legacy_messages():
    from app.database.db import SessionLocal
    from datetime import datetime
    import json
    import uuid
    
    db = SessionLocal()
    try:
        convs = db.query(Conversation).filter(
            Conversation.messages.isnot(None),
            Conversation.messages != "[]",
            Conversation.messages != ""
        ).all()
        
        if convs:
            print(f"[MIGRATION] Found {len(convs)} conversations to migrate.")
            for c in convs:
                try:
                    msgs = json.loads(c.messages)
                    if not msgs:
                        c.messages = "[]"
                        continue
                    
                    for m in msgs:
                        created_at = datetime.utcnow()
                        if m.get("createdAt"):
                            try:
                                created_at = datetime.fromisoformat(m.get("createdAt").replace("Z", "+00:00"))
                            except Exception:
                                pass
                        
                        db_msg = Message(
                            id=m.get("id") or str(uuid.uuid4()),
                            conversation_id=c.id,
                            role=m.get("role"),
                            content=m.get("content"),
                            created_at=created_at
                        )
                        db.add(db_msg)
                    
                    c.messages = "[]"
                    db.commit()
                except Exception as ex:
                    db.rollback()
                    print(f"[MIGRATION ERROR] Failed to migrate conversation {c.id}: {ex}")
            print("[MIGRATION] Migration completed successfully.")
    except Exception as e:
        print(f"[MIGRATION ERROR] Migration failed: {e}")
    finally:
        db.close()

migrate_legacy_messages()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="PROTON SOLUTIONS API",
    description="Enterprise-grade AI platform backend",
    version="1.0.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https?://proton-solutions.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Duration: {process_time:.3f}s"
    )
    
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Health check
@app.get("/")
async def root():
    return {
        "name": "PROTON SOLUTIONS API",
        "version": "1.0.0",
        "status": "operational",
        "environment": settings.environment
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(newsletter.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(settings_route.router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.environment == "development"
    )
