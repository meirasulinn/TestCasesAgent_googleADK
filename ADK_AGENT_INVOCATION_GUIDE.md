# Google ADK Agent Invocation Guide

Based on analysis of the Google ADK package installed in your venv, here's the complete pattern for properly invoking agents.

## Overview

- **LlmAgent** (aliased as `Agent`) is the main agent class for LLM-based interactions
- **Runner** manages execution of agents within sessions
- Agents **must** be run through the **Runner**, not directly
- All invocation is **async** - there is no synchronous execution method on agents
- Input/output is handled via **pydantic schemas** through `input_schema` and `output_schema` fields

---

## Key Method Signatures

### LlmAgent Methods (from BaseAgent)

#### `run_async(parent_context: InvocationContext) -> AsyncGenerator[Event, None]`
```python
# ONLY method to invoke an agent - runs async generator that yields Events
# - parent_context: InvocationContext created by Runner
# - Yields: Event objects representing agent execution steps
# - This is an INTERNAL method called by Runner, you should NOT call directly
# - Always async - no sync version exists for agent execution
```

#### Constructor Parameters
```python
class LlmAgent(BaseAgent):
    name: str                                           # Agent name (required, unique in tree)
    model: Union[str, BaseLlm] = ''                    # LLM model ("gemini-2.0-flash", etc)
    instruction: Union[str, InstructionProvider] = '' # Agent's system instructions
    static_instruction: Optional[types.ContentUnion] = None  # Static cached instructions
    
    # INPUT/OUTPUT CONTROL
    input_schema: Optional[type[BaseModel]] = None     # Pydantic model for agent input
    output_schema: Optional[type[BaseModel]] = None    # Pydantic model for agent output
    output_key: Optional[str] = None                   # Session state key for output
    
    # TOOLS
    tools: list[ToolUnion] = []                        # Available tools/functions
    
    # GENERATION CONFIG
    generate_content_config: Optional[types.GenerateContentConfig] = None
    
    # CALLBACKS (all support sync or async, single or list)
    before_model_callback: Optional[BeforeModelCallback] = None
    after_model_callback: Optional[AfterModelCallback] = None
    before_tool_callback: Optional[BeforeToolCallback] = None
    after_tool_callback: Optional[AfterToolCallback] = None
    on_tool_error_callback: Optional[OnToolErrorCallback] = None
    
    # ADVANCED
    planner: Optional[BasePlanner] = None              # Planning/thinking
    code_executor: Optional[BaseCodeExecutor] = None   # Code execution
```

### Runner Methods

#### `__init__` - Runner initialization
```python
class Runner:
    def __init__(
        self,
        *,
        app: Optional[App] = None,                          # App containing agent (preferred)
        app_name: Optional[str] = None,                     # App name (if app not provided)
        agent: Optional[BaseAgent] = None,                  # Root agent (if app not provided)
        plugins: Optional[List[BasePlugin]] = None,         # Plugin list (deprecated, use app)
        artifact_service: Optional[BaseArtifactService] = None,
        session_service: BaseSessionService,               # REQUIRED
        memory_service: Optional[BaseMemoryService] = None,
        credential_service: Optional[BaseCredentialService] = None,
    ):
        # Either provide 'app' OR both 'app_name' + 'agent' (not both patterns)
        pass
```

#### `run()` - Synchronous execution (for testing/convenience only)
```python
def run(
    self,
    *,
    user_id: str,
    session_id: str,
    new_message: types.Content,
    run_config: Optional[RunConfig] = None,
) -> Generator[Event, None, None]:
    """Synchronous wrapper around run_async for local testing.
    
    Args:
        user_id: User ID for the session
        session_id: Session ID (must already exist in session_service)
        new_message: types.Content with role='user' (appended to session)
        run_config: Optional RunConfig with streaming/audio settings
        
    Yields:
        Event objects from agent execution
        
    Note: Uses background thread internally - not for production
    """
```

#### `run_async()` - Asynchronous execution (RECOMMENDED for production)
```python
async def run_async(
    self,
    *,
    user_id: str,
    session_id: str,
    invocation_id: Optional[str] = None,                # Resume interrupted invocation
    new_message: Optional[types.Content] = None,        # User message to add
    state_delta: Optional[dict[str, Any]] = None,       # Session state changes
    run_config: Optional[RunConfig] = None,             # Streaming/audio config
) -> AsyncGenerator[Event, None]:
    """Main production method to run agent.
    
    Args:
        user_id: User ID for the session
        session_id: Session ID (must already exist in session_service)
        invocation_id: Resume mode - set to resume a paused invocation
        new_message: User message (required if not resuming)
        state_delta: Optional state modifications to apply
        run_config: Optional RunConfig (streaming, audio, LLM call limits, etc.)
        
    Yields:
        Event objects representing each step of agent execution
        
    Raises:
        ValueError: If session not found, or both invocation_id and new_message are None
        
    Important:
        - This is THE method for running agents
        - All execution happens through this async generator
        - Session must already exist (created via session_service)
        - Must iterate through all events to complete agent run
    """
```

---

## How to Invoke: Complete Pattern

### Step 1: Create or Retrieve a Session

```python
from google.adk.sessions import InMemorySessionService
from google.adk.sessions import Session

session_service = InMemorySessionService()

# Create a new session
session = Session(
    app_name="my_app",
    user_id="user123",
    id="session456",
    state={},  # Initial state
)
await session_service.save_session(session)

# OR retrieve existing session
session = await session_service.get_session(
    app_name="my_app",
    user_id="user123", 
    session_id="session456"
)
```

### Step 2: Define Your Agent with Input/Output Schemas

```python
from pydantic import BaseModel
from google.adk import Agent

class TestCaseInput(BaseModel):
    """Input specification for test case generation."""
    spec_file: str
    num_cases: int = 5

class TestCaseOutput(BaseModel):
    """Output - generated test cases."""
    test_cases: list[str]
    total_generated: int

# Create agent with schemas
agent = Agent(
    name="test_case_generator",
    model="gemini-2.0-flash",
    instruction="You are a test case generation expert. Generate test cases based on the input specification.",
    input_schema=TestCaseInput,        # Incoming data model
    output_schema=TestCaseOutput,      # Outgoing data model
    output_key="generated_test_cases", # Store output in session state
)
```

### Step 3: Create a Runner

```python
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService

session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()

runner = Runner(
    app_name="test_case_app",
    agent=agent,
    session_service=session_service,
    artifact_service=artifact_service,
)
```

### Step 4: Execute Agent and Process Events

```python
import asyncio
from google.genai import types

async def run_agent():
    # Prepare user message (will be validated against input_schema)
    user_message = types.Content(
        role='user',
        parts=[types.Part(text='''
            Here is the spec file: test_spec.json
            Generate 10 test cases
        ''')]
    )
    
    # Run agent and collect events
    async for event in runner.run_async(
        user_id="user123",
        session_id="session456",
        new_message=user_message,
    ):
        print(f"Event from {event.author}: {event.actions}")
        
        # Events have:
        # - event.author: str (agent name that generated this)
        # - event.actions: EventActions with content, state_delta, etc
        # - event.content: types.Content (agent's response)
        # - event.is_final_response(): bool (True when agent done)

# Run it
asyncio.run(run_agent())

# Retrieve output from session state
session = await session_service.get_session(
    app_name="test_case_app",
    user_id="user123",
    session_id="session456",
)
generated_output = session.state.get("generated_test_cases")
print(f"Generated test cases: {generated_output}")
```

---

## Complete Working Example

```python
import asyncio
from pydantic import BaseModel
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types


class TestSpec(BaseModel):
    """Input: test specification."""
    api_endpoint: str
    methods: list[str]


class TestCases(BaseModel):
    """Output: generated test cases."""
    cases: list[dict[str, str]]
    count: int


async def main():
    # 1. Setup services
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    
    # 2. Create agent with input/output schemas
    agent = Agent(
        name="api_test_generator",
        model="gemini-2.0-flash",
        instruction="""You are an API testing expert.
        Generate test cases for the given API endpoint and methods.
        Output must be valid JSON matching the TestCases schema.""",
        input_schema=TestSpec,
        output_schema=TestCases,
        output_key="test_results",
    )
    
    # 3. Create session FIRST (required by runner)
    from google.adk.sessions import Session
    session = Session(
        app_name="api_tester",
        user_id="tester_001",
        id="test_session_001",
        state={},
    )
    await session_service.save_session(session)
    
    # 4. Create runner
    runner = Runner(
        app_name="api_tester",
        agent=agent,
        session_service=session_service,
        artifact_service=artifact_service,
    )
    
    # 5. Prepare input message
    user_message = types.Content(
        role='user',
        parts=[types.Part(text="""
            API endpoint: https://api.example.com/users
            Methods: GET, POST, PUT, DELETE
            Generate comprehensive test cases.
        """)]
    )
    
    # 6. Run agent and process events
    print("Running agent...")
    event_count = 0
    async for event in runner.run_async(
        user_id="tester_001",
        session_id="test_session_001",
        new_message=user_message,
    ):
        event_count += 1
        print(f"\n[Event {event_count}] Author: {event.author}")
        print(f"  Final response: {event.is_final_response()}")
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(f"  Response: {part.text[:100]}...")
        if event.actions.state_delta:
            print(f"  State updated: {event.actions.state_delta.keys()}")
    
    # 7. Get results from session state
    final_session = await session_service.get_session(
        app_name="api_tester",
        user_id="tester_001",
        session_id="test_session_001",
    )
    
    results = final_session.state.get("test_results")
    print(f"\n✓ Final results: {results}")
    return results


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Event Structure

All agent execution communicates via `Event` objects:

```python
class Event:
    invocation_id: str              # Unique ID for this invocation
    author: str                     # Agent name that generated this event
    content: Optional[types.Content]  # The agent's response content
    actions: EventActions           # State changes, tool calls, transfers, etc.
    branch: Optional[str]           # Agent path (e.g., "root.sub_agent.child")
    
    # Helper methods:
    is_final_response(): bool       # True when agent has completed
    get_function_responses()        # Tool/function call results
    get_function_calls()            # Pending tool calls


class EventActions:
    state_delta: dict[str, Any]     # Session state changes
    artifact_delta: dict[str, int]  # Artifact versions changed
    transfer_to_agent: str          # If transferring to another agent
    rewind_before_invocation_id: str  # If rewinding
```

---

## Special Features

### 1. Input Schema Validation
- If `input_schema` is set, the agent receives structured input validation
- Use `output_key` to automatically store structured output in session state

### 2. Output Schema Validation  
- If `output_schema` is set, agent's response is parsed as JSON and validated
- Agent can ONLY reply (no tools/transfers allowed)
- Result stored at `session.state[output_key]`

### 3. Async-Only Pattern
```python
# ✓ CORRECT - async generator
async for event in runner.run_async(...):
    process(event)

# ✗ WRONG - no sync version exists
for event in agent.run(...):  # THIS METHOD DOESN'T EXIST
    process(event)
```

### 4. Callbacks (all async-compatible)
```python
async def before_model(callback_context, llm_request):
    """Called before LLM invocation."""
    # Can return modified request or custom response

async def after_tool(tool, args, tool_context, tool_response):
    """Called after tool execution."""
    # Can modify tool response

agent = Agent(
    name="my_agent",
    model="gemini-2.0-flash",
    instruction="...",
    before_model_callback=before_model,
    after_tool_callback=after_tool,
)
```

### 5. RunConfig for Streaming/Audio
```python
from google.adk.agents import RunConfig
from google.genai import types

config = RunConfig(
    streaming_mode="sse",  # Server-sent events
    speech_config=types.SpeechConfig(voice_config=types.VoiceConfig()),
    max_llm_calls=100,  # Limit LLM calls per invocation
)

async for event in runner.run_async(
    user_id="user123",
    session_id="session456", 
    new_message=user_message,
    run_config=config,
):
    process(event)
```

---

## Error Cases & Validation

```python
# ✗ Error: Session not found
await runner.run_async(user_id="u1", session_id="missing")
# → ValueError: Session not found: missing

# ✗ Error: Both new_message and invocation_id are None
await runner.run_async(user_id="u1", session_id="s1")
# → ValueError: Both invocation_id and new_message are None

# ✗ Error: Model not specified
agent = Agent(name="bad_agent", model="")  # No parent either
# → ValueError: No model found for bad_agent

# ✗ Error: output_schema without output_key
agent = Agent(
    name="agent",
    model="gemini-2.0-flash",
    output_schema=MySchema,  # Set schema
    output_key=None,  # But no key to store it
)  
# Results not stored in session state - probably not intended
```

---

## What Methods/Attributes Are Actually Exposed on LlmAgent

**Instance Methods (Public API):**
- `run_async(parent_context: InvocationContext)` - Execute agent (used by Runner)
- `run_live(parent_context: InvocationContext)` - Execute in video/audio mode
- `clone(update: Mapping[str, Any])` - Clone agent with modifications
- `find_agent(name: str)` - Find sub-agent by name
- `find_sub_agent(name: str)` - Find descendant by name

**Properties:**
- `root_agent` - Get root of agent tree
- `canonical_model` - Resolved model as BaseLlm instance
- `canonical_instruction()` - Resolved instruction string
- `canonical_tools()` - Resolved tools list
- `canonical_*_callbacks` - Resolved callbacks as lists

**Constructor Parameters (Full List):**
- `name`, `model`, `instruction`, `static_instruction`
- `tools`, `generate_content_config`
- `input_schema`, `output_schema`, `output_key`
- `before_model_callback`, `after_model_callback`
- `before_tool_callback`, `after_tool_callback`, `on_tool_error_callback`
- `planner`, `code_executor`
- `disallow_transfer_to_parent`, `disallow_transfer_to_peers`
- `include_contents`, `global_instruction`, `description`
- `sub_agents`, `before_agent_callback`, `after_agent_callback`

**NO Methods:**
- ❌ `.execute()` - Does not exist
- ❌ `.run()` - Sync version doesn't exist  
- ❌ Direct invocation - Must use Runner

---

## Why Your Current Code Fails

```python
# Your current code (WRONG):
class TestCaseAgent(Agent):
    def execute(self, input_data):  # ❌ execute() doesn't exist
        return {"status": "success"}

class TestCaseRunner(Runner):
    def run(self, input_data):  # ❌ Wrong signature
        result = agent.execute(input_data)  # ❌ execute() doesn't exist
        return result
```

**Problems:**
1. `Agent` (LlmAgent) doesn't have an `execute()` method
2. `Agent.run()` doesn't exist (only `run_async()`)
3. `Runner` should NOT be subclassed to add logic - use `run_async()`
4. Must use `Runner.run_async()` with proper parameters
5. Execution is **always async** - no sync path exists

---

## Requirements Summary

**For calling an agent, you MUST:**

1. ✓ Use `Runner` - agents cannot run standalone
2. ✓ Create/get a `Session` first 
3. ✓ Call `runner.run_async()` with user_id, session_id, new_message
4. ✓ Iterate through events with `async for`
5. ✓ Provide model and instructions to agent
6. ✓ Use `input_schema`/`output_schema` for structured data
7. ✓ Use `output_key` to store results in session state

**Requirements you do NOT need:**

- ❌ Sync execution - all async
- ❌ Custom Runner subclass - use base Runner class
- ❌ `.execute()` method - doesn't exist
- ❌ Direct agent invocation - must use Runner
- ❌ Manual thread management - Runner handles it with `run()` (if needed for testing)

---

## Direct File Locations in Your Venv

- **LlmAgent class**: `venv/Lib/site-packages/google/adk/agents/llm_agent.py` (917 lines)
- **Runner class**: `venv/Lib/site-packages/google/adk/runners.py` (1365 lines)  
- **BaseAgent class**: `venv/Lib/site-packages/google/adk/agents/base_agent.py` (659 lines)
- **Event class**: `venv/Lib/site-packages/google/adk/events/event.py`
- **InvocationContext**: `venv/Lib/site-packages/google/adk/agents/invocation_context.py`
- **RunConfig**: `venv/Lib/site-packages/google/adk/agents/run_config.py`
