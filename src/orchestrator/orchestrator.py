"""
Orchestrator - manages agents and coordinates user sessions using Google ADK.
Each user gets their own orchestrator instance with intelligent routing between agents.
Uses an LlmAgent as a router to decide which specialized agent to invoke.
"""
import logging
import json
from typing import Dict, Any, Optional, List
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types
from src.agents.base_agent import BaseAgent
from src.agents.test_case_agent import TestCaseAgent
from src.agents.weather_agent import WeatherAgent
from src.agents.time_agent import TimeAgent
from src.services.session_manager import SessionManager, session_manager
from src.services.faiss_service import FAISSService
from src.tools.file_parser_tool import FileParserTool
from src.config.settings import settings

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Multi-user orchestrator with LlmAgent-based routing.
    
    Features:
    - One instance per user
    - Uses LlmAgent as router to decide which specialized agent to invoke
    - Manages user session in Redis
    - Provides session-local FAISS
    - Dynamically registers multiple agents
    - Handles file uploads and chat with intelligent routing
    
    Architecture:
    - Router Agent (LlmAgent): Analyzes user request and returns agent name
    - Specialized Agents (e.g., TestCaseAgent): Execute specific tasks
    - Orchestrator: Coordinates between router and specialized agents
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
        
        # Agent registry
        self.agents: Dict[str, BaseAgent] = {}
        
        # ADK services for router
        self.adk_session_service = InMemorySessionService()
        self.adk_artifact_service = InMemoryArtifactService()
        
        # Router agent (will be created in initialize)
        self.router_agent: Optional[LlmAgent] = None
        self.router_runner: Optional[Runner] = None
        self.router_session_id: Optional[str] = None
        
        logger.info(f"Orchestrator created for user {user_id}")
    
    async def initialize(self):
        """Initialize orchestrator (create session, register agents, create router)."""
        # Ensure Redis session exists
        session = await self.session_manager.get_session(self.user_id)
        if not session:
            await self.session_manager.create_session(self.user_id)
            logger.info(f"Created new Redis session for user {self.user_id}")
        
        # Register agents
        test_case_agent = TestCaseAgent(
            user_id=self.user_id,
            session_manager=self.session_manager,
            faiss_service=self.faiss_service
        )
        self.agents["test_case_agent"] = test_case_agent
        
        # Register WeatherAgent
        weather_agent = WeatherAgent(
            user_id=self.user_id,
            session_manager=self.session_manager
        )
        self.agents["weather_agent"] = weather_agent
        
        # Register TimeAgent
        time_agent = TimeAgent(
            user_id=self.user_id,
            session_manager=self.session_manager
        )
        self.agents["time_agent"] = time_agent
        
        # Create router agent (LlmAgent that decides which agent to use)
        self.router_agent = LlmAgent(
            model=LiteLlm(model=settings.OPENAI_MODEL),
            name=f"router_agent_{self.user_id}",
            instruction=f"""You are an intelligent router for a multi-agent system.

Available agents:
- test_case_agent: Generates comprehensive test cases from product specifications
- weather_agent: Provides current weather information for cities worldwide
- time_agent: Provides current time information for different timezones

Your job:
1. Analyze the user's request
2. Determine which agent should handle it
3. Respond ONLY with the agent name (e.g., "test_case_agent")

Rules:
- If the request is about generating test cases, specifications, or testing → "test_case_agent"
- If the request is about weather, climate, or temperature → "weather_agent"
- If the request is about time, clock, or timezone → "time_agent"
- If unclear, choose the most relevant agent
- Respond with ONLY the agent name, nothing else"""
        )
        
        # Create ADK session for router
        adk_session = await self.adk_session_service.create_session(
            app_name=f"orchestrator_router_{self.user_id}",
            user_id=self.user_id
        )
        self.router_session_id = adk_session.id
        
        # Create Runner for router
        self.router_runner = Runner(
            app_name=f"orchestrator_router_{self.user_id}",
            agent=self.router_agent,
            session_service=self.adk_session_service,
            artifact_service=self.adk_artifact_service
        )
        
        logger.info(f"Orchestrator initialized for user {self.user_id} with {len(self.agents)} agents")
        logger.info(f"Router agent created: {self.router_agent.name}")
    
    async def handle_chat(self, message: str) -> Dict[str, Any]:
        """
        Handle chat message from user with intelligent agent routing.
        
        Args:
            message: User's message
        
        Returns:
            Response dict
        """
        logger.info(f"User {self.user_id} chat: {message[:100]}...")
        
        # Step 1: Use router agent to decide which agent to use
        agent_name = await self._route_to_agent(message)
        logger.info(f"Router selected agent: {agent_name}")
        
        # Step 2: Get the selected agent
        agent = self.agents.get(agent_name)
        if not agent:
            logger.warning(f"Agent {agent_name} not found, falling back to test_case_agent")
            agent = self.agents.get("test_case_agent")
        
        # Step 3: Execute with the selected agent
        # For test_case_agent, we need to pass "spec" instead of "message"
        if agent_name == "test_case_agent":
            result = await agent.process({
                "spec": message
            })
        else:
            result = await agent.process({
                "action": "chat",
                "message": message
            })
        
        return {
            "response": result.get("response", ""),
            "agent_used": agent_name,
            "test_cases": result.get("test_cases", []),
            "total_count": result.get("total_count", 0),
            "coverage_areas": result.get("coverage_areas", []),
            "source": "orchestrator_routing"
        }
    
    async def _route_to_agent(self, user_message: str) -> str:
        """
        Use router agent to decide which specialized agent should handle the request.
        
        Args:
            user_message: User's message
            
        Returns:
            Agent name (e.g., "test_case_agent")
        """
        # Prepare user message for router
        user_content = types.Content(
            role='user',
            parts=[types.Part(text=user_message)]
        )
        
        # Use stored router session
        if not self.router_session_id:
            logger.error(f"No router session found for user {self.user_id}")
            return "test_case_agent"  # fallback
        
        # Run router agent
        response_text = ""
        async for event in self.router_runner.run_async(
            user_id=self.user_id,
            session_id=self.router_session_id,
            new_message=user_content
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text
        
        # Extract agent name from response
        agent_name = response_text.strip().lower()
        logger.info(f"Router agent returned: '{agent_name}'")
        
        # Validate agent exists
        if agent_name not in self.agents:
            logger.warning(f"Router returned invalid agent '{agent_name}', using test_case_agent")
            return "test_case_agent"
        
        return agent_name
    
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
        
        # Automatically generate test cases using routing
        logger.info(f"Auto-generating test cases for user {self.user_id}")
        
        request_message = f"""A specification file has been uploaded: '{file_name}'.
        
Please analyze the specification and generate comprehensive test cases.

Specification content:
{text_content}
"""
        
        result = await self.handle_chat(request_message)
        
        return {
            "response": f"File '{file_name}' uploaded successfully. {result.get('response', '')}",
            "file_name": file_name,
            "test_cases": result.get("test_cases", []),
            "total_count": result.get("total_count", 0),
            "coverage_areas": result.get("coverage_areas", []),
            "source": result.get("source", "orchestrator_routing"),
            "agent_used": result.get("agent_used")
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
