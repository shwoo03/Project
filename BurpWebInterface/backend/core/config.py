"""
Application Configuration
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 10006
    DEBUG: bool = True
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:10007", "http://localhost:3000", "http://localhost:5173"]
    
    # Burp Suite MCP
    BURP_MCP_HOST: str = "localhost"
    BURP_MCP_PORT: int = 9999  # Default Burp MCP port
    BURP_MCP_TIMEOUT: int = 30
    
    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30
    
    # Database (optional)
    DATABASE_URL: str = "sqlite+aiosqlite:///./burp_web.db"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
