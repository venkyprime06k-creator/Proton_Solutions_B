import os
from typing import List
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Settings:
    """Simple settings class without Pydantic parsing issues"""
    
    # Server
    port: int = int(os.getenv("PORT", "8000"))
    environment: str = os.getenv("ENVIRONMENT", "development")
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "")
    
    # JWT
    jwt_secret: str = os.getenv("JWT_SECRET", "your_super_secret_key_change_this")
    jwt_expiry_minutes: int = int(os.getenv("JWT_EXPIRY_MINUTES", "1440"))
    
    # AI Providers
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    default_ai_provider: str = os.getenv("DEFAULT_AI_PROVIDER", "groq")
    
    # Rate Limiting
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    
    # CORS Origins - Parse safely
    cors_origins: List[str] = []
    
    def __init__(self):
        # Parse CORS origins from environment variable
        cors_env = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
        if cors_env:
            # Split by comma and clean up
            self.cors_origins = [origin.strip() for origin in cors_env.split(",") if origin.strip()]
        
        # Validate required settings
        if not self.database_url:
            raise ValueError("DATABASE_URL is required in .env file")
        if not self.jwt_secret:
            raise ValueError("JWT_SECRET is required in .env file")
    
    def __repr__(self):
        return f"Settings(environment={self.environment}, database_url={self.database_url[:50]}...)"

# Create single instance
settings = Settings()

# Print confirmation
print(f"[SUCCESS] Settings loaded successfully")
print(f"   Environment: {settings.environment}")
print(f"   CORS Origins: {settings.cors_origins}")
print(f"   Database: {settings.database_url[:50]}...")