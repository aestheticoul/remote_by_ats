import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 10000))
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    
    # CORS settings for production
    ALLOWED_ORIGINS: list = [
        "https://your-app-name.onrender.com",
        "http://localhost:3000",
        "http://localhost:8000"
    ]
    
    # WebSocket settings
    WS_MAX_SIZE: int = 16 * 1024 * 1024  # 16MB
    WS_PING_INTERVAL: int = 20
    WS_PING_TIMEOUT: int = 10

settings = Settings()
