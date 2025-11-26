"""
Base abstract class for all agents in the system.
All agents inherit from this and use Google ADK LlmAgent.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
from google.adk.agents import LlmAgent

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    
    Features:
    - Google ADK LlmAgent integration
    - Access to Redis (via SessionManager)
    - Optional FAISS for semantic search
    - Unified interface for all agents
    """
    
    def __init__(
        self,
        name: str,
        user_id: str,
        session_manager,
        faiss_service=None
    ):
        """
        Initialize base agent.
        
        Args:
            name: Agent name
            user_id: User this agent is serving
            session_manager: Redis session manager
            faiss_service: Optional FAISS service for this session
        """
        self.name = name
        self.user_id = user_id
        self.session_manager = session_manager
        self.faiss_service = faiss_service
        
        logger.info(f"Agent {name} initialized for user {user_id}")
    
    @abstractmethod
    def create_adk_agent(self) -> LlmAgent:
        """
        Create and configure the Google ADK LlmAgent.
        Must be implemented by subclasses.
        
        Returns:
            Configured LlmAgent instance
        """
        pass
    
    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process user request and return response.
        Must be implemented by subclasses.
        
        Args:
            input_data: Input data dict (e.g., {"message": "..."})
        
        Returns:
            Response dict (e.g., {"response": "...", "source": "agent_name"})
        """
        pass
