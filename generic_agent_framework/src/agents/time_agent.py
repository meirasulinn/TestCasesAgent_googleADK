"""
TimeAgent - Simple agent that provides current time information.
This is an EXAMPLE agent showing how to create agents with function tools.
"""
import logging
from typing import Dict, Any
from datetime import datetime, timezone, timedelta
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types
from src.agents.base_agent import BaseAgent
from config.settings import settings

logger = logging.getLogger(__name__)


class TimeAgent(BaseAgent):
    """
    Example agent that provides current time information.
    Uses a simple function tool that ADK converts automatically.
    """
    
    def __init__(self, user_id: str, session_manager, faiss_service=None):
        """Initialize TimeAgent."""
        self.model = settings.OPENAI_MODEL
        
        super().__init__(
            name="TimeAgent",
            user_id=user_id,
            session_manager=session_manager,
            faiss_service=faiss_service
        )
        
        # Create ADK agent with function tool
        self.adk_agent = self.create_adk_agent()
        
        # ADK services
        self.adk_session_service = InMemorySessionService()
        self.adk_artifact_service = InMemoryArtifactService()
        
        logger.info(f"TimeAgent created for user {user_id}")
    
    def create_adk_agent(self) -> LlmAgent:
        """
        Create Google ADK LlmAgent with function tool.
        ADK automatically converts Python functions to tools.
        
        Returns:
            Configured LlmAgent instance
        """
        # Define time tool function (ADK will convert it to a tool)
        def get_current_time(location: str = "UTC") -> str:
            """
            Get the current time for a location.
            
            Args:
                location: Location name (e.g., "Israel", "New York", "UTC")
                
            Returns:
                Current time as a string
            """
            # Get current UTC time
            now = datetime.now(timezone.utc)
            
            # Approximate timezone offsets (simplified for demo)
            timezone_offsets = {
                "israel": 2,
                "tel aviv": 2,
                "jerusalem": 2,
                "new york": -5,
                "london": 0,
                "tokyo": 9,
                "paris": 1,
                "los angeles": -8,
                "utc": 0
            }
            
            location_lower = location.lower()
            offset_hours = timezone_offsets.get(location_lower, 0)
            
            # Calculate local time
            local_time = now + timedelta(hours=offset_hours)
            
            time_str = local_time.strftime("%I:%M %p")
            date_str = local_time.strftime("%A, %B %d, %Y")
            
            return f"Current time in {location}: {time_str} on {date_str} (UTC{offset_hours:+d})"
        
        instruction = """You are a helpful time assistant.

Your task: Provide current time information when users ask.

When a user asks about time:
1. Extract the location from their request
2. Use the get_current_time function to get the time
3. Present the information in a friendly way

If the user doesn't specify a location, assume UTC.

Be helpful and concise.
"""
        
        # Create LlmAgent with function tool (ADK auto-converts to tool)
        agent = LlmAgent(
            model=LiteLlm(model=self.model),
            name=self.name,
            instruction=instruction,
            tools=[get_current_time]  # ADK automatically converts to tool
        )
        
        return agent
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process user request for time information.
        
        Args:
            input_data: Dict with "message" key
        
        Returns:
            Response dict with time information
        """
        message = input_data.get("message", "")
        
        logger.info(f"TimeAgent processing: {message[:100]}...")
        
        # Create ADK session for this request
        adk_session = await self.adk_session_service.create_session(
            app_name=f"time_agent_{self.user_id}",
            user_id=self.user_id
        )
        
        # Create Runner
        runner = Runner(
            app_name=f"time_agent_{self.user_id}",
            agent=self.adk_agent,
            session_service=self.adk_session_service,
            artifact_service=self.adk_artifact_service
        )
        
        # Prepare user message
        user_content = types.Content(
            role='user',
            parts=[types.Part(text=message)]
        )
        
        # Run agent and collect response
        response_text = ""
        async for event in runner.run_async(
            user_id=self.user_id,
            session_id=adk_session.id,
            new_message=user_content
        ):
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text'):
                        response_text += part.text
        
        return {
            "response": response_text.strip(),
            "source": "time_agent"
        }
