"""
Configuration settings for the multi-agent system.
All settings use environment variables with sensible defaults.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Global configuration for the system."""
    
    # OpenAI via LiteLLM (used by Google ADK)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")
    
    # Ensure API key is in environment for LiteLLM
    if OPENAI_API_KEY:
        os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    
    # Redis configuration
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6381"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    
    # Session management
    SESSION_TTL: int = int(os.getenv("SESSION_TTL", "3600"))  # 1 hour default
    
    # FAISS configuration
    FAISS_DIMENSION: int = int(os.getenv("FAISS_DIMENSION", "1536"))  # OpenAI embedding dimension
    FAISS_SIMILARITY_THRESHOLD: float = float(os.getenv("FAISS_SIMILARITY_THRESHOLD", "0.85"))
    
    # API configuration
    API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
    API_PORT: int = int(os.getenv("API_PORT", "8100"))
    
    # Google ADK configuration
    ADK_APP_NAME: str = os.getenv("ADK_APP_NAME", "test_case_generator")
    
    @classmethod
    def validate(cls):
        """Validate required settings."""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required")
        return True


# Global settings instance
settings = Settings()
