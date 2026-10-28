"""
Application configuration using pydantic-settings.

WHAT: Centralized config from environment variables
WHY: Type-safe, validated config with sensible defaults
HOW: Pydantic BaseSettings reads from .env and environment
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Literal
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment."""
    
    # App metadata
    APP_NAME: str = "DealForge"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "sqlite:///./data/marketplace.db"
    
    # LLM Provider Selection
    LLM_PROVIDER: Literal["lm_studio", "openrouter"] = "lm_studio"
    
    # LM Studio Configuration
    LM_STUDIO_BASE_URL: str = "http://localhost:1234/v1"
    LM_STUDIO_DEFAULT_MODEL: str = "qwen/qwen3-1.7b"
    LM_STUDIO_TIMEOUT: int = 30  # seconds
    
    # LLM Request Configuration
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_DELAY: int = 2  # seconds, base for exponential backoff
    LLM_DEFAULT_TEMPERATURE: float = 0.0  # Phase 2: deterministic by default
    LLM_DEFAULT_MAX_TOKENS: int = 2048  # Increased to allow longer messages with reasoning
    
    # OpenRouter Configuration
    LLM_ENABLE_OPENROUTER: bool = False
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_DEFAULT_MODEL: str = "google/gemini-2.5-flash-lite"
    
    # Phase 2: Negotiation Configuration
    MAX_NEGOTIATION_ROUNDS: int = 10
    MIN_NEGOTIATION_ROUNDS: int = 2  # Minimum rounds before buyer can decide
    PARALLEL_SELLER_LIMIT: int = 10  # Max concurrent seller responses (up to 10 for demo)
    ORCHESTRATOR: Literal["asyncio", "langgraph"] = "langgraph"
    
    # CORS - accepts comma-separated string or list
    # Use str type and parse in validator to avoid JSON parsing issues
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from comma-separated string or list."""
        if isinstance(v, list):
            return ",".join(v)
        if isinstance(v, str):
            # Return as-is (will be split when used)
            return v
        return v
    
    def get_cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./data/logs/app.log"
    LOGS_DIR: str = "./data/logs/sessions"
    LOG_RETENTION_DAYS: int = 7
    AUTO_SAVE_NEGOTIATIONS: bool = True
    
    # Session Management
    SESSION_CLEANUP_HOURS: int = 1  # TTL for active_rooms cache

    # RAG (credit card info / uploads)
    RAG_DATA_DIR: str = "./data/rag"
    RAG_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 50
    
    # Streaming / SSE
    SSE_HEARTBEAT_INTERVAL: int = 15  # seconds between heartbeat events
    SSE_RETRY_TIMEOUT: int = 5  # seconds for SSE retry timeout
    
    class Config:
        # Look for .env in project root (Hack_NYU/.env) first, then backend/.env
        env_file = [
            str(Path(__file__).parent.parent.parent.parent / ".env"),  # Hack_NYU/.env
            str(Path(__file__).parent.parent.parent / ".env"),  # backend/.env (fallback)
        ]
        env_file_encoding = "utf-8"
        case_sensitive = True


# Singleton instance
settings = Settings()

