"""
Orchestrator - manages agents and coordinates user sessions using Google ADK.
Each user gets their own orchestrator instance with intelligent routing between agents.
Uses an LlmAgent as a router to decide which specialized agent to invoke.
"""
import logging
from typing import Dict, Any, Optional
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types
from src.agents.base_agent import BaseAgent
from src.agents.time_agent import TimeAgent
from src.agents.weather_agent import WeatherAgent
from src.services.session_manager import SessionManager, session_manager
from src.services.faiss_service import FAISSService
from config.settings import settings

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Multi-user orchestrator with LlmAgent-based routing.
    
    Features:
    - One instance per user
    - Uses LlmAgent as router to decide which specialized agent to invoke
    - Manages user session in Redis
    - Provides optional per-user FAISS
    - Dynamically registers multiple agents
    - Handles chat with intelligent routing
    
    Architecture:
    - Router Agent (LlmAgent): Analyzes user request and returns agent name
    - Specialized Agents (e.g., TimeAgent): Execute specific tasks
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
        self.faiss_service = FAISSService(user_id)  # Optional - remove if not needed
        
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
        
        # ========================================
        # REGISTER YOUR AGENTS HERE
        # ========================================
        
        # Example Agent 1: TimeAgent
        time_agent = TimeAgent(
            user_id=self.user_id,
            session_manager=self.session_manager,
            faiss_service=self.faiss_service  # Optional
        )
        self.agents["time_agent"] = time_agent
        
        # Example Agent 2: WeatherAgent
        weather_agent = WeatherAgent(
            user_id=self.user_id,
            session_manager=self.session_manager,
            faiss_service=self.faiss_service  # Optional
        )
        self.agents["weather_agent"] = weather_agent
        
        # TODO: Add your custom agents here
        # Example:
        # your_agent = YourAgent(
        #     user_id=self.user_id,
        #     session_manager=self.session_manager,
        #     faiss_service=self.faiss_service
        # )
        # self.agents["your_agent"] = your_agent
        
        # ========================================
        # CREATE ROUTER AGENT
        # ========================================
        
        # Update this instruction when you add new agents
        router_instruction = f"""You are an intelligent router for a multi-agent system.

Available agents:
- time_agent: Provides current time information for different timezones
- weather_agent: Provides weather information for cities worldwide

Your job:
1. Analyze the user's request
2. Determine which agent should handle it
3. Respond ONLY with the agent name (e.g., "time_agent")

Rules:
- If the request is about time, clock, or timezone → "time_agent"
- If the request is about weather, climate, or temperature → "weather_agent"
- If unclear, choose the most relevant agent
- Respond with ONLY the agent name, nothing else

Examples:
User: "What time is it in New York?" → time_agent
User: "What's the weather in London?" → weather_agent
User: "Is it raining in Tokyo?" → weather_agent
User: "What's the time in Israel?" → time_agent
"""
        
        self.router_agent = LlmAgent(
            model=LiteLlm(model=settings.OPENAI_MODEL),
            name=f"router_agent_{self.user_id}",
            instruction=router_instruction
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
            logger.warning(f"Agent {agent_name} not found, using first available agent")
            agent = list(self.agents.values())[0] if self.agents else None
            if not agent:
                return {
                    "response": "No agents available",
                    "error": "No agents registered"
                }
        
        # Step 3: Execute with the selected agent
        result = await agent.process({
            "message": message
        })
        
        return {
            "response": result.get("response", ""),
            "agent_used": agent_name,
            "source": "orchestrator_routing"
        }
    
    async def _route_to_agent(self, user_message: str) -> str:
        """
        Use router agent to decide which specialized agent should handle the request.
        
        Args:
            user_message: User's message
            
        Returns:
            Agent name (e.g., "time_agent")
        """
        # Prepare user message for router
        user_content = types.Content(
            role='user',
            parts=[types.Part(text=user_message)]
        )
        
        # Run router agent
        response_text = ""
        async for event in self.router_runner.run_async(
            user_id=self.user_id,
            session_id=self.router_session_id,
            new_message=user_content
        ):
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text'):
                        response_text += part.text
        
        # Extract agent name
        agent_name = response_text.strip().lower()
        
        # Validate
        if agent_name not in self.agents:
            logger.warning(f"Router returned invalid agent: {agent_name}, using default")
            agent_name = list(self.agents.keys())[0] if self.agents else "unknown"
        
        return agent_name


# Global orchestrator registry (one per user)
_orchestrators: Dict[str, Orchestrator] = {}


async def get_orchestrator(user_id: str) -> Orchestrator:
    """
    Get or create orchestrator for a user.
    
    Args:
        user_id: User identifier
    
    Returns:
        Orchestrator instance
    """
    if user_id not in _orchestrators:
        orchestrator = Orchestrator(user_id)
        await orchestrator.initialize()
        _orchestrators[user_id] = orchestrator
        logger.info(f"Created new orchestrator for user {user_id}")
    
    return _orchestrators[user_id]
