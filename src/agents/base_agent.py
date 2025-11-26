"""
Base abstract class for all agents in the system.
All agents inherit from this and use Google ADK LlmAgent.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
from google.adk.agents import LlmAgent
from src.services.session_manager import SessionManager
from src.services.faiss_service import FAISSService
from src.config.settings import settings

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    Each agent initializes its own shared FAISS and Redis prefix by agent type.
    """
    def __init__(
        self,
        name: str,
        user_id: str,
        session_manager: SessionManager,
        model: Optional[str] = None
    ):
        self.name = name
        self.user_id = user_id
        self.session_manager = session_manager
        agent_type = name.lower().replace("agent", "")
        self.faiss_service = FAISSService(agent_type)
        self.cache_prefix = f"{agent_type}:"
        self.model = model or settings.OPENAI_MODEL
        self.adk_agent: Optional[LlmAgent] = None
        logger.info(f"BaseAgent {name} for user {user_id} - using shared FAISS '{agent_type}'")
    
    @abstractmethod
    def create_adk_agent(self) -> LlmAgent:
        """
        Create and configure the Google ADK LlmAgent.
        Must be implemented by subclasses.
        
        Returns:
            Configured Google ADK LlmAgent instance
        """
        pass
    
    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input and return results.
        Must be implemented by subclasses.
        
        Args:
            input_data: Input data for the agent
        
        Returns:
            Processing results
        """
        pass
    
    async def get_session_data(self) -> Optional[Dict[str, Any]]:
        """Get session data for this agent's user."""
        return await self.session_manager.get_session(self.user_id)
    
    async def update_session_data(self, updates: Dict[str, Any]):
        """Update session data for this agent's user."""
        await self.session_manager.update_session(self.user_id, updates)
    
    async def get_cache(self, key: str) -> Optional[Any]:
        """Get data from agent-type global cache."""
        full_key = f"{self.cache_prefix}{key}"
        return await self.session_manager.get_cache(full_key)

    async def set_cache(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set data in agent-type global cache."""
        full_key = f"{self.cache_prefix}{key}"
        await self.session_manager.set_cache(full_key, value, ttl)
    
    def search_session_data(self, query: str, top_k: int = 3) -> list:
        """Search user's session data using FAISS."""
        return self.faiss_service.search(query, top_k)
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} user={self.user_id}>"
