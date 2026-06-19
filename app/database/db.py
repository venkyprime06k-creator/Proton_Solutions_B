from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.config.settings import settings

# Get database URL
database_url = settings.database_url
if database_url and database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

# Create engine
engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False  # Set to True to see SQL queries
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for models
Base = declarative_base()

# Dependency for FastAPI
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Test connection function - FIXED VERSION
def test_connection():
    try:
        with engine.connect() as conn:
            # Use text() for raw SQL queries
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print("[SUCCESS] Connected to PostgreSQL successfully!")
            print(f"   Version: {version[:60]}...")
            return True
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return False
