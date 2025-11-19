"""
Correct ADK Agent Invocation Pattern - Complete Working Example

This demonstrates the PROPER way to:
1. Create an LlmAgent with input/output schemas
2. Set up a Runner  
3. Invoke the agent and process results
4. Handle events and retrieve output

All code uses async/await - there is NO synchronous execution path in ADK.
"""

import asyncio
from pydantic import BaseModel
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService, Session
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types


# ============================================================================
# 1. DEFINE INPUT/OUTPUT SCHEMAS (Pydantic Models)
# ============================================================================

class TestCaseInput(BaseModel):
    """Input specification for test case generation."""
    api_endpoint: str
    description: str
    methods: list[str] = ["GET", "POST", "PUT", "DELETE"]


class TestCaseOutput(BaseModel):
    """Output: Generated test cases."""
    test_cases: list[dict[str, str]]  # Each test case is {name, description}
    total_count: int
    coverage_areas: list[str]


# ============================================================================
# 2. CREATE THE AGENT
# ============================================================================

def create_test_case_agent() -> Agent:
    """
    Creates an LlmAgent configured to generate test cases.
    
    Key Points:
    - Uses input_schema to validate incoming data structure
    - Uses output_schema to validate LLM response matches expected format
    - output_key stores the structured result in session.state
    - All execution happens through Runner.run_async()
    """
    return Agent(
        name="test_case_generator",
        model="gemini-2.0-flash",  # or your preferred model
        
        # Instructions for the LLM
        instruction="""You are an expert QA engineer specializing in API testing.
Generate comprehensive test cases for the provided API endpoint.

Instructions:
1. Analyze the endpoint and HTTP methods provided
2. Generate test cases covering:
   - Happy path scenarios
   - Error handling
   - Edge cases
   - Security considerations
3. Return test cases as valid JSON

Format your response as JSON matching this structure:
{
  "test_cases": [
    {"name": "test case 1", "description": "..."},
    {"name": "test case 2", "description": "..."}
  ],
  "total_count": 5,
  "coverage_areas": ["happy path", "error handling", "security"]
}
""",
        
        # Schemas for structured I/O
        input_schema=TestCaseInput,      # Incoming data validation
        output_schema=TestCaseOutput,    # Outgoing data validation
        output_key="generated_test_cases",  # Where to store result in state
    )


# ============================================================================
# 3. SETUP SERVICES (Session, Artifacts, etc)
# ============================================================================

async def setup_services():
    """
    Initialize ADK services. In production, you'd use:
    - VertexAiSessionService (Google Cloud)
    - GcsArtifactService (Google Cloud Storage)
    - etc.
    
    For this example, we use in-memory services for testing.
    """
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    
    return session_service, artifact_service


# ============================================================================
# 4. CREATE SESSION (Required before running agent)
# ============================================================================

async def create_session(
    session_service: InMemorySessionService,
    app_name: str,
    user_id: str,
    session_id: str,
) -> Session:
    """
    Sessions represent conversation threads between a user and agents.
    Runner requires the session to already exist.
    """
    session = Session(
        app_name=app_name,
        user_id=user_id,
        id=session_id,
        state={},  # Initial session state (empty for new sessions)
    )
    await session_service.save_session(session)
    return session


# ============================================================================
# 5. CREATE RUNNER
# ============================================================================

def create_runner(
    app_name: str,
    agent: Agent,
    session_service,
    artifact_service,
) -> Runner:
    """
    Runner orchestrates agent execution.
    
    Key parameters:
    - app_name: Name of your application
    - agent: The root agent to execute
    - session_service: Where to store/retrieve sessions
    - artifact_service: Where to store/retrieve artifacts
    """
    runner = Runner(
        app_name=app_name,
        agent=agent,
        session_service=session_service,
        artifact_service=artifact_service,
    )
    return runner


# ============================================================================
# 6. RUN AGENT AND PROCESS EVENTS
# ============================================================================

async def run_agent_and_get_results(
    runner: Runner,
    user_id: str,
    session_id: str,
    user_input: str,
) -> dict:
    """
    Execute the agent and collect results.
    
    This is the core pattern:
    1. Prepare user message
    2. Call runner.run_async() with required parameters
    3. Iterate through events with async for
    4. Process each event
    5. Return collected results
    """
    
    # Prepare the user message
    user_message = types.Content(
        role='user',
        parts=[types.Part(text=user_input)]
    )
    
    print("\n" + "=" * 70)
    print(f"RUNNING AGENT: {runner.agent.name}")
    print("=" * 70)
    
    events_collected = []
    
    # THIS IS THE MAIN INVOCATION PATTERN - async generator
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_message,
    ):
        # Each event represents a step in agent execution
        events_collected.append(event)
        
        # Display event information
        print(f"\n[Event {len(events_collected)}]")
        print(f"  Author: {event.author}")
        print(f"  Invocation ID: {event.invocation_id}")
        print(f"  Is Final Response: {event.is_final_response()}")
        
        # Show agent response if present
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    text_preview = part.text[:150].replace('\n', ' ')
                    print(f"  Response: {text_preview}...")
        
        # Show state changes if any
        if event.actions.state_delta:
            print(f"  State Updates: {list(event.actions.state_delta.keys())}")
            for key, value in event.actions.state_delta.items():
                if isinstance(value, (str, int, float, bool)):
                    print(f"    {key} = {value}")
                else:
                    print(f"    {key} = {type(value).__name__} (length: {len(value)})")
    
    print(f"\nTotal events collected: {len(events_collected)}")
    return {
        "event_count": len(events_collected),
        "events": events_collected,
    }


# ============================================================================
# 7. RETRIEVE RESULTS FROM SESSION STATE
# ============================================================================

async def get_results_from_session(
    session_service: InMemorySessionService,
    app_name: str,
    user_id: str,
    session_id: str,
    output_key: str,
) -> dict:
    """
    After agent execution, retrieve structured output from session state.
    """
    # Fetch the updated session
    session = await session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )
    
    if not session:
        raise ValueError(f"Session not found: {session_id}")
    
    # The output_schema result is stored at output_key
    result = session.state.get(output_key)
    
    print(f"\n✓ Retrieved results from session.state['{output_key}']:")
    print(f"  Type: {type(result).__name__}")
    if isinstance(result, dict):
        print(f"  Keys: {list(result.keys())}")
        for key, value in result.items():
            if isinstance(value, list):
                print(f"    {key}: list with {len(value)} items")
            else:
                print(f"    {key}: {value}")
    
    return result


# ============================================================================
# 8. MAIN ORCHESTRATION
# ============================================================================

async def main():
    """
    Complete example of calling an ADK agent.
    
    Demonstrates:
    - Creating agent with schemas
    - Setting up services
    - Creating runner
    - Executing with run_async()
    - Processing events
    - Retrieving structured output
    """
    
    # Configuration
    APP_NAME = "test_case_generator_app"
    USER_ID = "qa_engineer_001"
    SESSION_ID = "session_test_20250119"
    OUTPUT_KEY = "generated_test_cases"
    
    # User input for the agent
    USER_INPUT = """
    I need test cases for this API:
    
    Endpoint: https://api.example.com/users/{id}
    Methods: GET, PUT, DELETE
    
    Description: User management API - allows fetching, updating, and deleting user profiles
    
    Please generate comprehensive test cases covering happy paths, errors, and edge cases.
    """
    
    print("\n" + "#" * 70)
    print("# ADK AGENT INVOCATION COMPLETE EXAMPLE")
    print("#" * 70)
    
    # Step 1: Create agent
    print("\n[1] Creating agent...")
    agent = create_test_case_agent()
    print(f"    Agent: {agent.name}")
    print(f"    Model: {agent.model}")
    print(f"    Input Schema: {agent.input_schema.__name__ if agent.input_schema else 'None'}")
    print(f"    Output Schema: {agent.output_schema.__name__ if agent.output_schema else 'None'}")
    
    # Step 2: Setup services
    print("\n[2] Setting up services...")
    session_service, artifact_service = await setup_services()
    print(f"    Session service: {type(session_service).__name__}")
    print(f"    Artifact service: {type(artifact_service).__name__}")
    
    # Step 3: Create session
    print("\n[3] Creating session...")
    session = await create_session(
        session_service,
        APP_NAME,
        USER_ID,
        SESSION_ID,
    )
    print(f"    Session ID: {session.id}")
    print(f"    User ID: {session.user_id}")
    print(f"    Initial state: {session.state}")
    
    # Step 4: Create runner
    print("\n[4] Creating runner...")
    runner = create_runner(
        APP_NAME,
        agent,
        session_service,
        artifact_service,
    )
    print(f"    Runner app_name: {runner.app_name}")
    print(f"    Root agent: {runner.agent.name}")
    
    # Step 5: Execute agent
    print("\n[5] Executing agent...")
    execution_results = await run_agent_and_get_results(
        runner,
        USER_ID,
        SESSION_ID,
        USER_INPUT,
    )
    
    # Step 6: Retrieve structured output
    print("\n[6] Retrieving structured output...")
    output = await get_results_from_session(
        session_service,
        APP_NAME,
        USER_ID,
        SESSION_ID,
        OUTPUT_KEY,
    )
    
    # Step 7: Process results
    print("\n[7] Processing results...")
    if output:
        print(f"    ✓ Generated {output.get('total_count', 0)} test cases")
        if isinstance(output.get('test_cases'), list):
            for i, tc in enumerate(output['test_cases'][:3], 1):
                print(f"      • {tc.get('name', 'Unknown')}")
            if len(output['test_cases']) > 3:
                print(f"      ... and {len(output['test_cases']) - 3} more")
    else:
        print("    ⚠ No output retrieved")
    
    print("\n" + "#" * 70)
    print("# EXECUTION COMPLETE")
    print("#" * 70 + "\n")
    
    return output


# ============================================================================
# RUN THE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Run the async main function
    result = asyncio.run(main())
    print(f"\nFinal result type: {type(result)}")
    print(f"Final result: {result}")
