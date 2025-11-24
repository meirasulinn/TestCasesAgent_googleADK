"""
FastAPI application with multi-user orchestration using Google ADK.
"""
from fastapi import FastAPI, File, UploadFile, HTTPException, Header
from fastapi.responses import JSONResponse
from typing import Optional
import logging
from pydantic import BaseModel
from src.orchestrator.orchestrator import get_orchestrator
from src.config.settings import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Validate settings
try:
    settings.validate()
    logger.info("Settings validated successfully")
except ValueError as e:
    logger.error(f"Settings validation failed: {e}")
    raise

app = FastAPI(
    title="Multi-Agent Test Case Generator",
    version="2.0",
    description="Multi-user test case generation system using Google ADK"
)


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    user_id: str


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    test_cases: Optional[list] = None
    coverage_areas: Optional[list] = None
    source: Optional[str] = None


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Multi-Agent Test Case Generator API",
        "version": "2.0",
        "features": [
            "Multi-user orchestration",
            "Google ADK agents",
            "OpenAI via LiteLLM",
            "Redis session management",
            "FAISS session-local search",
            "Automatic test case generation"
        ]
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint - user sends a message.
    
    The orchestrator will:
    1. Check if user has uploaded files
    2. If yes, generate test cases
    3. If no, prompt user to upload a file
    """
    try:
        logger.info(f"Chat request from user {request.user_id}")
        
        # Get user's orchestrator
        orchestrator = await get_orchestrator(request.user_id)
        
        # Handle chat
        result = await orchestrator.handle_chat(request.message)
        
        return ChatResponse(**result)
    
    except Exception as e:
        logger.error(f"Chat error for user {request.user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Header(..., description="Unique user identifier")
):
    """
    Upload specification file and automatically generate test cases.
    
    Args:
        file: Uploaded file (PDF, TXT, JSON)
        user_id: User identifier from header
    
    Returns:
        Generated test cases
    """
    try:
        logger.info(f"File upload from user {user_id}: {file.filename}")
        
        # Get user's orchestrator
        orchestrator = await get_orchestrator(user_id)
        
        # Read file content
        file_content = await file.read()
        
        # Handle file upload
        result = await orchestrator.handle_file_upload(
            file_content=file_content,
            file_name=file.filename or "unknown",
            content_type=file.content_type or ""
        )
        
        return JSONResponse(content=result)
    
    except Exception as e:
        logger.error(f"Upload error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/{user_id}")
async def get_session(user_id: str):
    """
    Get session information for a user.
    
    Args:
        user_id: User identifier
    
    Returns:
        Session info
    """
    try:
        orchestrator = await get_orchestrator(user_id)
        info = await orchestrator.get_session_info()
        return info
    
    except Exception as e:
        logger.error(f"Session info error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "system": "Multi-Agent Test Case Generator",
        "components": {
            "orchestrator": "active",
            "adk_agents": "active",
            "redis": "configured",
            "faiss": "active",
            "openai": "configured via LiteLLM"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level="info"
    )
