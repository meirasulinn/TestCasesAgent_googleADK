"""
FastAPI REST API for the generic agent framework.
Provides endpoints for chat, health check, and session management.
"""
import logging
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from src.orchestrator.orchestrator import get_orchestrator
from src.services.session_manager import session_manager
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Generic Agent Framework",
    description="Multi-agent system with intelligent routing using Google ADK",
    version="1.0.0"
)


# ========================================
# REQUEST/RESPONSE MODELS
# ========================================

class ChatRequest(BaseModel):
    """Chat request model."""
    message: str


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    agent_used: str
    source: str = "orchestrator"


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    redis_connected: bool
    timestamp: str
    agents_available: int = 2


# ========================================
# ENDPOINTS
# ========================================

@app.get("/", response_model=dict)
async def root():
    """Root endpoint."""
    return {
        "message": "Generic Agent Framework API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health():
    """
    Health check endpoint.
    Verifies Redis connection and system status.
    """
    redis_connected = False
    try:
        await session_manager.connect()
        await session_manager.redis_client.ping()
        redis_connected = True
    except Exception as e:
        logger.error(f"Health check failed: {e}")
    
    return HealthResponse(
        status="healthy" if redis_connected else "degraded",
        redis_connected=redis_connected,
        timestamp=datetime.utcnow().isoformat(),
        agents_available=2  # time_agent, weather_agent
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_id: Optional[str] = Header(None, alias="user-id")
):
    """
    Chat endpoint - send message to agent system.
    Router automatically selects appropriate agent.
    
    Headers:
        user-id: User identifier (required)
    
    Body:
        message: User's message
    
    Returns:
        Agent response
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user-id header is required")
    
    try:
        # Get orchestrator for user
        orchestrator = await get_orchestrator(user_id)
        
        # Handle chat
        result = await orchestrator.handle_chat(request.message)
        
        return ChatResponse(
            response=result.get("response", ""),
            agent_used=result.get("agent_used", "unknown"),
            source=result.get("source", "orchestrator")
        )
    except Exception as e:
        logger.error(f"Chat error for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/{user_id}", response_model=dict)
async def get_session(user_id: str):
    """
    Get session data for a user.
    
    Args:
        user_id: User identifier
    
    Returns:
        Session data
    """
    try:
        session = await session_manager.get_session(user_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# STARTUP/SHUTDOWN
# ========================================

@app.on_event("startup")
async def startup():
    """Initialize on startup."""
    logger.info("Starting Generic Agent Framework API")
    logger.info(f"OpenAI Model: {settings.OPENAI_MODEL}")
    logger.info(f"Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    
    # Validate settings
    try:
        settings.validate()
        logger.info("Settings validated successfully")
    except ValueError as e:
        logger.error(f"Settings validation failed: {e}")
        raise


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    logger.info("Shutting down Generic Agent Framework API")
    await session_manager.disconnect()
