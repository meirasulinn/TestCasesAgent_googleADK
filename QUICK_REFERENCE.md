# Quick Reference: ADK Agent Invocation

## TL;DR - How to Call an Agent

```python
import asyncio
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types

async def main():
    # 1. Create agent (config object)
    agent = Agent(
        name="my_agent",
        model="gemini-2.0-flash",
        instruction="You are helpful.",
    )
    
    # 2. Setup session service
    session_service = InMemorySessionService()
    
    # 3. Create session (REQUIRED)
    session = Session(app_name="app", user_id="u1", id="s1", state={})
    await session_service.save_session(session)
    
    # 4. Create runner
    runner = Runner(
        app_name="app",
        agent=agent,
        session_service=session_service,
    )
    
    # 5. Run agent via async generator
    msg = types.Content(role='user', parts=[types.Part(text="Your prompt")])
    async for event in runner.run_async(
        user_id="u1",
        session_id="s1",
        new_message=msg,
    ):
        print(f"Agent: {event.content}")

asyncio.run(main())
```

---

## LlmAgent Methods That Can Be Called

| Method | Callable? | Use Case |
|--------|-----------|----------|
| `run_async(context)` | ❌ No | Internal use only (called by Runner) |
| `run_live(context)` | ❌ No | Internal use only (for audio/video) |
| `execute()` | ❌ No | **Does not exist** |
| `run()` | ❌ No | **Does not exist** |
| `clone(update)` | ✓ Yes | Clone agent with modifications |
| `find_agent(name)` | ✓ Yes | Find sub-agent by name |

**To invoke an agent: Use `runner.run_async()` ← This is the ONLY way**

---

## Constructor Parameters: Agent vs Runner

### Agent Constructor (for creating agents)

**Required:**
- `name: str` - Unique identifier for agent

**Very Common:**
- `model: str` - LLM model name ("gemini-2.0-flash", etc)
- `instruction: str` - Agent's system instructions

**For Structured I/O:**
- `input_schema: type[BaseModel]` - Pydantic model for input validation
- `output_schema: type[BaseModel]` - Pydantic model for output validation  
- `output_key: str` - Session state key to store output

**Optional:**
- `tools: list` - Available tools
- `sub_agents: list[Agent]` - Child agents
- `generate_content_config: dict` - LLM settings
- Callbacks: `before_model_callback`, `after_tool_callback`, etc.

### Runner Constructor (for running agents)

**Required:**
- Either: `app: App` 
- Or both: `app_name: str` + `agent: Agent`
- Plus: `session_service: BaseSessionService`

**Optional:**
- `artifact_service` - For file storage
- `memory_service` - For long-term memory
- `credential_service` - For auth

---

## Running an Agent: Step by Step

### Step 1: Prepare Agent Config
```python
agent = Agent(
    name="test_generator",
    model="gemini-2.0-flash",
    instruction="Generate test cases...",
    input_schema=InputModel,      # Validates user input
    output_schema=OutputModel,    # Validates agent output
    output_key="test_cases",      # Where to store result
)
```

### Step 2: Create Session (Must Exist!)
```python
from google.adk.sessions import Session, InMemorySessionService

session_service = InMemorySessionService()

session = Session(
    app_name="my_app",
    user_id="user_123",
    id="session_abc",
    state={},  # Empty initial state
)

await session_service.save_session(session)
```

### Step 3: Create Runner
```python
runner = Runner(
    app_name="my_app",
    agent=agent,
    session_service=session_service,
)
```

### Step 4: Execute Agent
```python
from google.genai import types

user_message = types.Content(
    role='user',
    parts=[types.Part(text="Generate 5 test cases for login")]
)

# This is the invocation - always async
async for event in runner.run_async(
    user_id="user_123",
    session_id="session_abc",
    new_message=user_message,
):
    # Process each event
    if event.is_final_response():
        print("Agent finished")
```

### Step 5: Retrieve Results
```python
# Results stored in session.state at output_key
final_session = await session_service.get_session(
    app_name="my_app",
    user_id="user_123",
    session_id="session_abc",
)

results = final_session.state["test_cases"]
```

---

## What Each Event Contains

```python
class Event:
    invocation_id: str                 # Unique run ID
    author: str                        # Agent name
    content: types.Content             # Agent's response
    
    # Helper methods:
    is_final_response() -> bool        # True when done
    get_function_calls() -> list       # Pending tool calls
    get_function_responses() -> list   # Tool results
    
    actions:
        - state_delta: dict            # Session state changes
        - artifact_delta: dict         # Files changed
        - transfer_to_agent: str       # Transfer target
```

---

## Common Patterns

### Pattern 1: Simple Text Response
```python
agent = Agent(
    name="assistant",
    model="gemini-2.0-flash",
    instruction="Answer questions.",
)

async for event in runner.run_async(user_id="u1", session_id="s1", new_message=msg):
    if event.is_final_response():
        print(event.content.parts[0].text)
```

### Pattern 2: Structured Input/Output
```python
class Request(BaseModel):
    task: str
    detail_level: int

class Response(BaseModel):
    result: str
    confidence: float

agent = Agent(
    name="analyzer",
    model="gemini-2.0-flash",
    input_schema=Request,
    output_schema=Response,
    output_key="analysis",
)

# After run_async():
final_session = await session_service.get_session(...)
result: Response = final_session.state["analysis"]
```

### Pattern 3: With Tools
```python
def multiply(a: int, b: int) -> int:
    return a * b

agent = Agent(
    name="calculator",
    model="gemini-2.0-flash",
    tools=[multiply],  # Pass functions as tools
    instruction="Use tools to calculate.",
)
```

### Pattern 4: Sub-agents
```python
researcher = Agent(name="researcher", ...)
writer = Agent(name="writer", ...)

orchestrator = Agent(
    name="orchestrator",
    sub_agents=[researcher, writer],
    instruction="Coordinate sub-agents.",
)

runner = Runner(..., agent=orchestrator)
```

### Pattern 5: Callbacks (for custom logic)
```python
async def before_llm(context, request):
    print(f"About to call LLM")
    return None  # Don't intercept, let LLM run

async def after_tool(tool, args, context, response):
    print(f"Tool {tool.name} returned: {response}")
    return response  # Use tool response as-is

agent = Agent(
    name="monitored",
    model="gemini-2.0-flash",
    before_model_callback=before_llm,
    after_tool_callback=after_tool,
)
```

---

## Error Handling

```python
try:
    async for event in runner.run_async(...):
        pass
except ValueError as e:
    if "Session not found" in str(e):
        print("Create session first!")
    elif "Both invocation_id and new_message are None" in str(e):
        print("Provide a message or invocation_id")
```

---

## Sync vs Async

**For Production:**
```python
# ✓ Use async (recommended)
async for event in runner.run_async(...):
    pass
```

**For Testing/CLI:**
```python
# ✓ Can use sync wrapper (uses background thread)
for event in runner.run(...):
    pass
```

**DO NOT DO:**
```python
# ❌ No sync path for agent.run_async()
event = await agent.run_async()  # Wrong - requires InvocationContext

# ❌ No execute() method
result = agent.execute(data)  # AttributeError

# ❌ No direct invocation
for event in agent.run():  # Method doesn't exist
```

---

## Configuration: RunConfig

```python
from google.adk.agents import RunConfig
from google.genai import types

config = RunConfig(
    streaming_mode="sse",  # Enable server-sent events
    speech_config=types.SpeechConfig(...),
    max_llm_calls=100,  # Limit calls
    save_live_audio=True,
)

async for event in runner.run_async(
    user_id="u1",
    session_id="s1",
    new_message=msg,
    run_config=config,  # Pass config here
):
    pass
```

---

## Session Management

```python
# Get existing session
session = await session_service.get_session(
    app_name="app",
    user_id="user1",
    session_id="session1",
)

# Check if session exists
if session:
    print(f"State: {session.state}")
    print(f"History: {len(session.events)} events")

# Session state is updated by agent
# State is stored as dict[str, Any]
session.state["key"] = "value"
```

---

## Files to Reference

In your venv:

```
google.adk/
├── agents/
│   ├── llm_agent.py          ← LlmAgent class (917 lines)
│   ├── base_agent.py         ← BaseAgent class (659 lines)
│   ├── invocation_context.py ← InvocationContext (409 lines)
│   ├── run_config.py         ← RunConfig
│   └── ...
├── runners.py                ← Runner class (1365 lines)
├── sessions/
│   ├── session.py            ← Session class
│   └── base_session_service.py
└── events/
    └── event.py              ← Event class
```

---

## The ONLY Way to Invoke

```python
# This is the pattern. No other way works.
async for event in runner.run_async(
    user_id=...,
    session_id=...,
    new_message=...,
):
    process_event(event)
```

**Everything else is either:**
- ❌ Wrong (e.g., `agent.execute()`)
- ❌ Internal use (e.g., `agent.run_async()` directly)
- ✓ Support functions (e.g., `agent.clone()`, `agent.find_agent()`)
