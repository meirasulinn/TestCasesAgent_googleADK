"""
BaseTool interface for all tools in the system.
Tools are shared utilities that agents can use.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """
    Abstract base class for all tools.
    
    Tools provide specific functionality that agents can leverage:
    - API connectors
    - File parsers
    - Data processors
    - External service integrations
    """
    
    def __init__(self, name: str, description: str):
        """
        Initialize base tool.
        
        Args:
            name: Tool name
            description: Tool description
        """
        self.name = name
        self.description = description
        logger.info(f"Tool {name} initialized")
    
    @abstractmethod
    async def run_async(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool asynchronously.
        Must be implemented by subclasses.
        
        Args:
            input_data: Input parameters for the tool
        
        Returns:
            Tool execution results
        """
        pass
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name}>"
