"""
WeatherAgent - Simple agent that provides weather information.
Demonstrates ADK function tool integration (works with OpenAI models).
"""
import logging
from typing import Dict, Any
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types
from src.agents.base_agent import BaseAgent
from src.config.settings import settings

logger = logging.getLogger(__name__)


class WeatherAgent(BaseAgent):
    """
    Agent that provides weather information.
    Uses a simple function tool that ADK converts automatically.
    Works with OpenAI models!
    """
    def __init__(self, user_id: str, session_manager):
        """Initialize WeatherAgent."""
        self.model = settings.OPENAI_MODEL
        super().__init__(
            name="WeatherAgent",
            user_id=user_id,
            session_manager=session_manager
        )
        
        # Create ADK agent with function tool
        self.adk_agent = self.create_adk_agent()
        
        # ADK services
        self.adk_session_service = InMemorySessionService()
        self.adk_artifact_service = InMemoryArtifactService()
        
        logger.info(f"WeatherAgent created for user {user_id} with function tool")
    
    def create_adk_agent(self) -> LlmAgent:
        """
        Create Google ADK LlmAgent with function tool.
        ADK automatically converts Python functions to tools.
        
        Returns:
            Configured LlmAgent instance
        """
        # Define weather tool function (ADK will convert it to a tool)
        def get_weather(city: str) -> str:
            """
            Get current weather for a city.
            
            Args:
                city: Name of the city
                
            Returns:
                Weather information string
            """
            # Mock weather data (for demo purposes)
            weather_db = {
                "new york": {"temp": 22, "condition": "Sunny", "humidity": 45},
                "london": {"temp": 15, "condition": "Cloudy", "humidity": 70},
                "tokyo": {"temp": 18, "condition": "Rainy", "humidity": 80},
                "tel aviv": {"temp": 28, "condition": "Sunny", "humidity": 55},
                "israel": {"temp": 26, "condition": "Clear", "humidity": 50},
                "jerusalem": {"temp": 24, "condition": "Partly Cloudy", "humidity": 48},
                "paris": {"temp": 17, "condition": "Cloudy", "humidity": 60},
                "los angeles": {"temp": 25, "condition": "Sunny", "humidity": 40}
            }
            
            city_lower = city.lower()
            if city_lower in weather_db:
                w = weather_db[city_lower]
                return f"Weather in {city}: {w['condition']}, {w['temp']}°C, Humidity: {w['humidity']}%"
            else:
                return f"Weather in {city}: Sunny, 20°C, Humidity: 50% (default data)"
        
        instruction = """You are a helpful weather assistant.

Your task: Provide weather information for cities when users ask.

When a user asks about weather:
1. Extract the city name from their request
2. Use the get_weather function to get weather data
3. Present the information in a friendly way

If the user doesn't specify a city, ask them which city they're interested in.

Be helpful and concise.
"""
        
        # Create LlmAgent with function tool (ADK auto-converts to tool)
        agent = LlmAgent(
            model=LiteLlm(model=self.model),
            name=f"weather_agent_{self.user_id}",
            instruction=instruction,
            description="Provides weather information for cities",
            tools=[get_weather]  # ADK converts function to tool
        )
        
        return agent
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process weather request using ADK Runner.
        
        Args:
            input_data: {
                "message": str - user's weather request
            }
        
        Returns:
            {
                "response": str - weather information
            }
        """
        message = input_data.get("message", "")
        
        if not message.strip():
            return {
                "response": "Please ask me about the weather in a specific city!",
                "error": False
            }
        
        logger.info(f"WeatherAgent processing request for user {self.user_id}: {message[:50]}...")
        
        # Create or get ADK session
        session_id = f"weather_{self.user_id}_{hash(message) % 10000}"
        
        try:
            session = await self.adk_session_service.create_session(
                app_name="weather_agent",
                user_id=self.user_id,
                session_id=session_id
            )
        except Exception as e:
            logger.warning(f"Session may already exist: {e}")
            session_id = session_id
        
        # Create Runner
        runner = Runner(
            app_name="weather_agent",
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
                            logger.info(f"WeatherAgent event: {part.text[:100]}...")
        except Exception as e:
            logger.error(f"WeatherAgent error: {e}")
            return {
                "response": f"Sorry, I encountered an error: {str(e)}",
                "error": True
            }
        
        logger.info(f"WeatherAgent response: {response_text[:100]}...")
        
        return {
            "response": response_text.strip(),
            "error": False
        }
