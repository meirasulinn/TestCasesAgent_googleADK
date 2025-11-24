"""
Orchestrator - manages agents and coordinates user sessions.
Each user gets their own orchestrator instance.
"""
import logging
from typing import Dict, Any, Optional
from src.agents.test_case_agent import TestCaseAgent
from src.services.session_manager import SessionManager, session_manager
from src.services.faiss_service import FAISSService
from src.tools.file_parser_tool import FileParserTool

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Multi-user orchestrator using Google ADK.
    
    Features:
    - One instance per user
    - Manages user session in Redis
    - Provides session-local FAISS
    - Coordinates agents (currently TestCaseAgent)
    - Handles file uploads and chat
    """
    
    def __init__(self, user_id: str):
        """
        Initialize orchestrator for a specific user.
        
        Args:
            user_id: Unique user identifier
        """
        self.user_id = user_id
        self.session_manager = session_manager
        self.faiss_service = FAISSService(user_id)
        
        # Tools
        self.file_parser = FileParserTool()
        
        # Agents
        self.test_case_agent: Optional[TestCaseAgent] = None
        
        logger.info(f"Orchestrator created for user {user_id}")
    
    async def initialize(self):
        """Initialize orchestrator (create session, initialize agents)."""
        # Ensure session exists
        session = await self.session_manager.get_session(self.user_id)
        if not session:
            await self.session_manager.create_session(self.user_id)
            logger.info(f"Created new session for user {self.user_id}")
        
        # Initialize TestCaseAgent
        self.test_case_agent = TestCaseAgent(
            user_id=self.user_id,
            session_manager=self.session_manager,
            faiss_service=self.faiss_service
        )
        
        logger.info(f"Orchestrator initialized for user {self.user_id}")
    
    async def handle_chat(self, message: str) -> Dict[str, Any]:
        """
        Handle chat message from user.
        
        Args:
            message: User's message
        
        Returns:
            Response dict
        """
        # Check if user has uploaded files
        session = await self.session_manager.get_session(self.user_id)
        if not session or not session.get("files"):
            return {
                "response": "Please upload a specification file first before chatting.",
                "requires_file": True
            }
        
        # For now, treat chat as a request to generate test cases from uploaded files
        files = session.get("files", [])
        if not files:
            return {
                "response": "No files found in your session. Please upload a file.",
                "requires_file": True
            }
        
        # Use the most recent file
        latest_file = files[-1]
        spec_text = latest_file.get("content", "")
        
        if not spec_text.strip():
            return {
                "response": "The uploaded file appears to be empty.",
                "error": True
            }
        
        # Generate test cases
        result = await self.test_case_agent.process({"spec": spec_text})
        
        return {
            "response": f"Generated {result.get('total_count', 0)} test cases.",
            "test_cases": result.get("test_cases", []),
            "coverage_areas": result.get("coverage_areas", []),
            "source": result.get("source", "unknown")
        }
    
    async def handle_file_upload(self, file_content: bytes, file_name: str, content_type: str) -> Dict[str, Any]:
        """
        Handle file upload from user.
        
        Args:
            file_content: File bytes
            file_name: File name
            content_type: Content type
        
        Returns:
            Response dict
        """
        logger.info(f"User {self.user_id} uploading file: {file_name}")
        
        # Parse file
        parse_result = await self.file_parser.run_async({
            "file_content": file_content,
            "file_name": file_name,
            "content_type": content_type
        })
        
        if not parse_result.get("success"):
            return {
                "response": f"Failed to parse file: {parse_result.get('error')}",
                "error": True
            }
        
        text_content = parse_result.get("text", "")
        
        # Add to session
        await self.session_manager.add_file_to_session(self.user_id, {
            "name": file_name,
            "type": parse_result.get("file_type"),
            "content": text_content,
            "size": len(file_content)
        })
        
        # Add to FAISS for semantic search
        self.faiss_service.add_document(
            text=text_content,
            metadata={"file_name": file_name, "type": "specification"}
        )
        
        # Automatically generate test cases
        logger.info(f"Auto-generating test cases for user {self.user_id}")
        result = await self.test_case_agent.process({"spec": text_content})
        
        return {
            "response": f"File '{file_name}' uploaded successfully. Generated {result.get('total_count', 0)} test cases.",
            "file_name": file_name,
            "test_cases": result.get("test_cases", []),
            "total_count": result.get("total_count", 0),
            "coverage_areas": result.get("coverage_areas", []),
            "source": result.get("source", "unknown")
        }
    
    async def get_session_info(self) -> Dict[str, Any]:
        """Get session information for this user."""
        session = await self.session_manager.get_session(self.user_id)
        if not session:
            return {"user_id": self.user_id, "session_exists": False}
        
        return {
            "user_id": self.user_id,
            "session_exists": True,
            "files_count": len(session.get("files", [])),
            "faiss_docs": self.faiss_service.size()
        }
    
    async def cleanup(self):
        """Clean up orchestrator resources."""
        logger.info(f"Cleaning up orchestrator for user {self.user_id}")
        # Could add cleanup logic here if needed


# Global orchestrator registry (one per user)
_orchestrators: Dict[str, Orchestrator] = {}


async def get_orchestrator(user_id: str) -> Orchestrator:
    """
    Get or create orchestrator for a user.
    
    Args:
        user_id: Unique user identifier
    
    Returns:
        Orchestrator instance for this user
    """
    if user_id not in _orchestrators:
        orchestrator = Orchestrator(user_id)
        await orchestrator.initialize()
        _orchestrators[user_id] = orchestrator
        logger.info(f"Created new orchestrator for user {user_id}")
    
    return _orchestrators[user_id]
