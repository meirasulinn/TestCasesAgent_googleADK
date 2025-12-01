"""
TimeAgent - Simple agent that provides current time information.
Demonstrates ADK function tool integration (works with OpenAI models).
"""
import logging
from typing import Dict, Any
from datetime import datetime, timezone
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types
from src.agents.base_agent import BaseAgent
from src.config.settings import settings

logger = logging.getLogger(__name__)


class TimeAgent(BaseAgent):
    """
    Agent that provides current time information.
    Uses a simple function tool that ADK converts automatically.
    Works with OpenAI models!
    """
    def __init__(self, user_id: str, session_manager):
        """Initialize TimeAgent."""
        self.model = settings.OPENAI_MODEL
        super().__init__(
            name="TimeAgent",
            user_id=user_id,
            session_manager=session_manager
        )
        
        # Create ADK agent with function tool
        self.adk_agent = self.create_adk_agent()
        
        # ADK services
        self.adk_session_service = InMemorySessionService()
        self.adk_artifact_service = InMemoryArtifactService()
        
        logger.info(f"TimeAgent created for user {user_id} with function tool")
    
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
            Get the current time.
            
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
            from datetime import timedelta
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

Common locations: Israel, New York, London, Tokyo, Paris, Los Angeles, UTC

Be helpful and concise.
"""
        
        # Create LlmAgent with function tool (ADK auto-converts to tool)
        agent = LlmAgent(
            model=LiteLlm(model=self.model),
            name=f"time_agent_{self.user_id}",
            instruction=instruction,
            description="Provides current time information",
            tools=[get_current_time]  # ADK converts function to tool
        )
        
        return agent
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process time request using ADK Runner.
        
        Args:
            input_data: {
                "message": str - user's time request,
                "history": list - conversation history (optional)
            }
        
        Returns:
            {
                "response": str - time information
            }
        """
        message = input_data.get("message", "")
        history = input_data.get("history", [])
        
        if not message.strip():
            return {
                "response": "Please ask me about the current time in a specific location!",
                "error": False
            }
        
        logger.info(f"TimeAgent processing request for user {self.user_id}: {message[:50]}...")
        
        # Create or get ADK session
        session_id = f"time_{self.user_id}_{hash(message) % 10000}"
        
        try:
            session = await self.adk_session_service.create_session(
                app_name="time_agent",
                user_id=self.user_id,
                session_id=session_id
            )
        except Exception as e:
            logger.warning(f"Session may already exist: {e}")
            session_id = session_id
        
        # Create Runner
        runner = Runner(
            app_name="time_agent",
            agent=self.adk_agent,
            session_service=self.adk_session_service,
            artifact_service=self.adk_artifact_service
        )
        
        # Build context from history if provided
        context_text = ""
        if history and len(history) > 0:
            context_text = "Previous conversation:\n"
            for idx, msg in enumerate(history[-3:], 1):  # Last 3 messages
                message_data = msg.get("message", {})
                user_msg = message_data.get("user_message", "")
                if user_msg:
                    context_text += f"{idx}. User: {user_msg}\n"
            context_text += "\nCurrent request:\n"
        
        # Prepare user message with context
        full_message = f"{context_text}{message}" if context_text else message
        user_content = types.Content(
            role='user',
            parts=[types.Part(text=full_message)]
        )
        
        # Run agent and collect response
        response_text = ""
        try:
            async for event in runner.run_async(
                user_id=self.user_id,
                session_id=session_id,
                new_message=user_content
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            response_text += part.text
                            logger.info(f"TimeAgent event: {part.text[:100]}...")
        except Exception as e:
            logger.error(f"TimeAgent error: {e}")
            return {
                "response": f"Sorry, I encountered an error: {str(e)}",
                "error": True
            }
        
        logger.info(f"TimeAgent response: {response_text[:100]}...")
        
        return {
            "response": response_text.strip(),
            "error": False
        }
