from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types
import os 
import asyncio

api_key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = api_key
model_name = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")

def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city."""
    return {"status": "success", "city": city, "time": "10:30 AM"}

agent_openai = LlmAgent(
    model=LiteLlm(model=model_name), # LiteLLM model string format
    name="openai_agent",
    instruction="You are a helpful assistant powered by GPT-4o.",
    # ... other agent parameters
    tools=[get_current_time]
)


# Standalone testing section
async def test_agent():
    """Test the agent using the correct ADK pattern."""
    
    APP_NAME = "test_app"
    USER_ID = "test_user"
    
    print("=== Testing OpenAI Agent ===")
    print(f"Model: {model_name}")
    print(f"Agent Name: {agent_openai.name}")
    print("-" * 50)
    
    # Setup services
    print("\n[Setup] Initializing services...")
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    
    # Create session
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
    )
    print("✓ Session created")
    
    # Create runner
    runner = Runner(
        app_name=APP_NAME,
        agent=agent_openai,
        session_service=session_service,
        artifact_service=artifact_service,
    )
    print("✓ Runner created")
    
    # Get session ID for reuse
    session_id = session.id
    
    # Test function
    async def run_test(test_name: str, user_input: str):
        print(f"\n[{test_name}]")
        print(f"Input: {user_input}")
        
        user_message = types.Content(
            role='user',
            parts=[types.Part(text=user_input)]
        )
        
        responses = []
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=user_message,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        responses.append(part.text)
        
        print(f"Response: {' '.join(responses)}")
        return responses
    
    # Run tests
    await run_test("Test 1", "Hello! Can you introduce yourself?")
    await run_test("Test 2", "What time is it in New York?")
    await run_test("Test 3", "Explain what you can do in one sentence.")
    await run_test("Test 4", "what did you check about new york")
    
    print("\n" + "=" * 50)
    print("Testing complete!")


if __name__ == "__main__":
    asyncio.run(test_agent())