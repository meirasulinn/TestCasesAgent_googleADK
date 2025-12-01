from fastapi import FastAPI, File, UploadFile, HTTPException, Header
from fastapi.responses import JSONResponse
from typing import Optional
from pydantic import BaseModel
import logging

from src.services.session_manager import session_manager
from src.services.mongo_session_history import MongoSessionHistory
from src.config.settings import settings
from src.orchestrator.orchestrator import get_orchestrator


# ================================================
# MODELS
# ================================================

class SessionHistoryResponse(BaseModel):
    history: list

class SessionListResponse(BaseModel):
    sessions: list

class NewSessionResponse(BaseModel):
    session_id: str

class ChatRequest(BaseModel):
    message: str
    user_id: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    test_cases: Optional[list] = None
    coverage_areas: Optional[list] = None
    source: Optional[str] = None


# ================================================
# APP INIT (יחיד!)
# ================================================

app = FastAPI(
    title="Multi-Agent Test Case Generator",
    version="2.0",
    description="Multi-user test case generation system using Google ADK"
)


# ================================================
# LOGGING SETUP
# ================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    settings.validate()
    logger.info("Settings validated successfully")
except ValueError as e:
    logger.error(f"Settings validation failed: {e}")
    raise


# ================================================
# USER ENDPOINTS
# ================================================

@app.get("/users", response_model=list)
async def get_all_users():
    """
    מחזיר את כל ה-user_id הייחודיים מתוך session_history.
    """
    mongo_history = MongoSessionHistory()
    pipeline = [
        {"$group": {"_id": "$user_id"}},
        {"$sort": {"_id": 1}}
    ]
    users = [doc["_id"] for doc in mongo_history.collection.aggregate(pipeline)]
    return users


# ================================================
# SESSION MANAGEMENT
# ================================================

@app.get("/sessions/{user_id}", response_model=SessionListResponse)
async def get_sessions(user_id: str):
    """
    Get all chat sessions (session_id) for a user.
    """
    sessions = session_manager.get_sessions_for_user(user_id)
    return SessionListResponse(sessions=sessions)


@app.post("/session/new/{user_id}", response_model=NewSessionResponse)
async def create_new_session(user_id: str):
    """
    Create a new chat session (session_id) for a user.
    """
    session_id = session_manager.create_session_for_user(user_id)
    return NewSessionResponse(session_id=session_id)


@app.get("/session/history/{user_id}/{session_id}", response_model=SessionHistoryResponse)
async def get_session_history(user_id: str, session_id: str):
    """
    Get chat history for a specific session_id.
    """
    mongo_history = MongoSessionHistory()
    history = mongo_history.get_history_by_session(session_id)
    return SessionHistoryResponse(history=history)


@app.get("/session/{user_id}")
async def get_session(user_id: str):
    """
    Get session information for a user.
    """
    info = {
        "user_id": user_id,
        "sessions": session_manager.get_sessions_for_user(user_id)
    }
    return info


# ================================================
# CHAT ENDPOINT (ORCHESTRATOR)
# ================================================

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint - user sends a message.
    מפעיל orchestrator ומחזיר תשובה אמיתית מהאייגנט.
    """
    try:
        logger.info(f"Chat request from user {request.user_id}, session_id={request.session_id}")
        orchestrator = await get_orchestrator(request.user_id)
        result = await orchestrator.handle_chat(request.message, session_id=request.session_id)
        return ChatResponse(
            response=result.get("response", ""),
            session_id=result.get("session_id", ""),
            test_cases=result.get("test_cases", []),
            coverage_areas=result.get("coverage_areas", []),
            source=result.get("source", "orchestrator")
        )
    except Exception as e:
        logger.error(f"Chat error for user {request.user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================================================
# FILE UPLOAD
# ================================================

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Header(..., description="Unique user identifier")
):
    """
    Upload specification file and automatically generate test cases.
    דמו בלבד.
    """
    try:
        logger.info(f"File upload from user {user_id}: {file.filename}")
        file_content = await file.read()
        result = {
            "message": f"הקובץ {file.filename} התקבל בהצלחה",
            "test_cases": [],
            "coverage_areas": [],
            "source": "demo"
        }
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Upload error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================================================
# ROOT + HEALTH
# ================================================

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


# ================================================
# ENTRY POINT
# ================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level="info"
    )
