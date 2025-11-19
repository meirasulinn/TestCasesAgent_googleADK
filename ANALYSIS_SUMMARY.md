# Google ADK Package Analysis - Executive Summary

## Investigation Scope

Searched the Google ADK package installed in your venv at:
```
c:\Users\liors\Desktop\adk_TestCaseAgent_poc\venv\Lib\site-packages\google\adk
```

Examined:
- ✓ LlmAgent class (lines 1-917)
- ✓ Runner class (lines 1-1365)
- ✓ BaseAgent class (lines 1-659)
- ✓ InvocationContext, RunConfig, Event classes
- ✓ All agent method signatures
- ✓ Input/output schema handling
- ✓ Event flow and processing

---

## Key Findings

### 1. LlmAgent Method Signatures

**Publicly Available Methods:**
```python
# On LlmAgent instances (extends BaseAgent):
agent.run_async(parent_context: InvocationContext) -> AsyncGenerator[Event]
agent.run_live(parent_context: InvocationContext) -> AsyncGenerator[Event]
agent.clone(update: Mapping[str, Any]) -> LlmAgent
agent.find_agent(name: str) -> Optional[Agent]
agent.find_sub_agent(name: str) -> Optional[Agent]
```

**Methods That DO NOT Exist:**
```python
agent.execute()  # ❌ Does not exist
agent.run()      # ❌ Does not exist (sync)
agent.run_async(...)  # ⚠️ Exists but INTERNAL - requires InvocationContext
```

### 2. Runner: How to Invoke Agents

**Constructor:**
```python
Runner(
    app_name: str,
    agent: Agent,
    session_service: BaseSessionService,
    artifact_service: Optional[BaseArtifactService] = None,
    memory_service: Optional[BaseMemoryService] = None,
    credential_service: Optional[BaseCredentialService] = None,
)
```

**Execution Methods:**
```python
# Synchronous (for testing)
runner.run(
    user_id: str,
    session_id: str,
    new_message: types.Content,
    run_config: Optional[RunConfig] = None,
) -> Generator[Event, None, None]

# Asynchronous (for production) ← RECOMMENDED
async def run_async(
    self,
    user_id: str,
    session_id: str,
    invocation_id: Optional[str] = None,
    new_message: Optional[types.Content] = None,
    state_delta: Optional[dict[str, Any]] = None,
    run_config: Optional[RunConfig] = None,
) -> AsyncGenerator[Event, None]
```

**Key Requirement: Session must exist before calling run_async()**

### 3. Input/Output Patterns

**Input Schema (User → Agent):**
```python
class MyInput(BaseModel):
    param1: str
    param2: int

agent = Agent(
    input_schema=MyInput,  # Validates incoming data
    ...
)
```

**Output Schema (Agent → Results):**
```python
class MyOutput(BaseModel):
    result: str
    confidence: float

agent = Agent(
    output_schema=MyOutput,     # Validates LLM response
    output_key="my_results",    # Store in session.state["my_results"]
    ...
)

# After execution:
session = await session_service.get_session(...)
output = session.state["my_results"]  # Type: MyOutput
```

### 4. Event Structure

All agent execution communicates via `Event` objects:

```python
class Event:
    invocation_id: str
    author: str  # Agent name
    content: Optional[types.Content]
    actions: EventActions
    branch: Optional[str]
    
    def is_final_response() -> bool
    def get_function_calls() -> list
    def get_function_responses() -> list
```

### 5. Async-Only Pattern

**There is NO synchronous path for agent execution.**

- `agent.run_async()` - async generator (INTERNAL only)
- `runner.run()` - sync wrapper using background thread (testing only)
- `runner.run_async()` - async generator (PRODUCTION ← use this)

```python
# ✓ Correct async pattern
async for event in runner.run_async(...):
    process(event)

# ✗ No sync method on agents
agent.execute(data)  # Doesn't exist
```

### 6. Structural Requirements

**Sessions are mandatory:**
```python
# Session MUST exist before runner.run_async()
session = Session(app_name="app", user_id="u1", id="s1", state={})
await session_service.save_session(session)

# Then run:
async for event in runner.run_async(
    user_id="u1",
    session_id="s1",
    new_message=message,
):
    pass
```

**Agents form trees:**
```python
root = Agent(
    name="root",
    sub_agents=[
        Agent(name="sub1", ...),
        Agent(name="sub2", ...),
    ]
)

runner = Runner(..., agent=root)
```

---

## What Your Code Did Wrong

```python
# ❌ WRONG PATTERNS IN YOUR CODE:

class TestCaseAgent(Agent):  # ❌ Agent isn't meant to be subclassed
    def execute(self, input_data):  # ❌ execute() doesn't exist

class TestCaseRunner(Runner):  # ❌ Runner shouldn't be subclassed
    def run(self, input_data):  # ❌ Wrong signature
        result = agent.execute(input_data)  # ❌ execute() doesn't exist
        return result
```

**Why:**
- Agent/LlmAgent is a Pydantic config object, not a base class to extend
- There is no `.execute()` method on agents
- All agent execution happens through `Runner.run_async()`
- Everything is async - no synchronous path exists
- Sessions must be pre-created

---

## Correct Pattern

```python
import asyncio
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types

async def main():
    # 1. Create agent (don't subclass)
    agent = Agent(
        name="test_generator",
        model="gemini-2.0-flash",
        instruction="Generate test cases",
    )
    
    # 2. Setup services
    session_service = InMemorySessionService()
    
    # 3. Create session (required!)
    session = Session(app_name="app", user_id="u1", id="s1", state={})
    await session_service.save_session(session)
    
    # 4. Create runner
    runner = Runner(
        app_name="app",
        agent=agent,
        session_service=session_service,
    )
    
    # 5. Execute via runner (not agent)
    message = types.Content(role='user', parts=[types.Part(text="...")])
    async for event in runner.run_async(
        user_id="u1",
        session_id="s1",
        new_message=message,
    ):
        if event.is_final_response():
            print(event.content)

asyncio.run(main())
```

---

## Documentation Provided

Created 4 comprehensive documents in your workspace:

### 1. **ADK_AGENT_INVOCATION_GUIDE.md** (Comprehensive Reference)
   - Complete method signatures
   - How to invoke agents step-by-step
   - Complete working example
   - Event structure
   - Special features (callbacks, streaming, etc.)
   - ~500 lines

### 2. **CORRECT_ADK_EXAMPLE.py** (Runnable Example)
   - Full working code you can execute
   - Creates agent with input/output schemas
   - Sets up services and runner
   - Demonstrates event processing
   - Shows how to retrieve results
   - ~300 lines, well-commented

### 3. **CURRENT_CODE_PROBLEMS.md** (Issue Analysis)
   - Detailed breakdown of each problem in your code
   - Why subclassing Agent/Runner is wrong
   - What methods actually exist
   - Common misunderstandings explained
   - Correct patterns for each scenario
   - ~400 lines

### 4. **QUICK_REFERENCE.md** (TL;DR Guide)
   - Quick lookup table
   - Minimal working example
   - Pattern templates
   - Error handling
   - Common patterns
   - Configuration reference
   - ~250 lines

---

## Critical Insights

### 1. No Execute Method
The most critical issue: `LlmAgent` has **NO** `.execute()` method or equivalent.

The **ONLY** way to run an agent is:
```python
async for event in runner.run_async(
    user_id=...,
    session_id=...,
    new_message=...,
):
    process(event)
```

### 2. Async Only
There is no synchronous execution path. Everything requires `async`/`await`.

The `runner.run()` synchronous method exists only for testing and uses a background thread internally.

### 3. Sessions Required
Agents don't operate in isolation. They run within `Session` objects that store:
- Conversation history
- State variables  
- Artifacts (files)
- User/app context

Session must be created **before** calling `runner.run_async()`.

### 4. Runner Orchestrates Everything
- Don't subclass `Runner`
- Don't call `agent.run_async()` directly (it requires `InvocationContext` which Runner creates)
- **Always** use `runner.run_async()`

### 5. Events Drive Communication
Agents don't return results directly. They yield `Event` objects that represent each step.

You must:
1. Iterate through all events with `async for`
2. Check `event.is_final_response()`
3. Retrieve results from `session.state` after execution

---

## Architecture Summary

```
┌──────────────────────────────────────────────────────────────┐
│                        Runner                                │
│                                                              │
│  run_async(user_id, session_id, new_message, run_config)   │
│         ↓                                                    │
│  Creates InvocationContext ← Session, State, Config        │
│         ↓                                                    │
│  agent.run_async(context) [Internal method]                │
│         ↓                                                    │
│  Yields Event objects with:                                │
│    - content (LLM response)                                │
│    - state_delta (state changes)                           │
│    - is_final_response()                                   │
│         ↓                                                    │
│  Updates session.state                                      │
│  Saves artifacts                                           │
└──────────────────────────────────────────────────────────────┘

User Code:
  async for event in runner.run_async(...):  ← THE ONLY ENTRY POINT
      process(event)
```

---

## Common Use Cases

### Use Case 1: Simple Query
```python
message = types.Content(role='user', parts=[types.Part(text="What is 2+2?")])
async for event in runner.run_async(..., new_message=message):
    if event.is_final_response():
        answer = event.content.parts[0].text
```

### Use Case 2: Structured Processing
```python
class Input(BaseModel):
    data: str

class Output(BaseModel):
    result: str

agent = Agent(
    name="processor",
    input_schema=Input,
    output_schema=Output,
    output_key="result",
)

# After run_async():
result = session.state["result"]  # Type: Output
```

### Use Case 3: Multi-Agent Workflow
```python
root = Agent(
    name="orchestrator",
    sub_agents=[
        Agent(name="analyzer", ...),
        Agent(name="reporter", ...),
    ]
)

runner = Runner(..., agent=root)
# Runner automatically coordinates sub-agents
```

### Use Case 4: Tool Integration
```python
def search(query: str) -> str:
    return "results..."

agent = Agent(
    name="searcher",
    tools=[search],
)
# Agent can call search() when needed
```

---

## Next Steps

1. **Use the QUICK_REFERENCE.md** for a quick lookup
2. **Study CORRECT_ADK_EXAMPLE.py** - it's a complete, runnable example
3. **Read CURRENT_CODE_PROBLEMS.md** - understand what was wrong
4. **Reference ADK_AGENT_INVOCATION_GUIDE.md** for detailed docs
5. **Refactor your code** using the correct patterns

---

## Bottom Line

✓ **Use the Agent + Runner pattern**
- Create `Agent(name=..., model=..., instruction=...)`
- Create `Runner(app_name=..., agent=..., session_service=...)`
- Call `runner.run_async(user_id=..., session_id=..., new_message=...)`
- Iterate through `Event` objects with `async for`
- Retrieve results from `session.state`

❌ **Don't do this**
- Subclass Agent or Runner
- Call `agent.execute()` (doesn't exist)
- Use sync execution in production
- Skip session creation
- Call `agent.run_async()` directly

---

## Files Referenced

All code examined is in your venv:
- `venv/Lib/site-packages/google/adk/agents/llm_agent.py` (917 lines)
- `venv/Lib/site-packages/google/adk/runners.py` (1365 lines)
- `venv/Lib/site-packages/google/adk/agents/base_agent.py` (659 lines)
- Plus ~50 other supporting files

Comprehensive method signatures and source code snippets extracted and documented.
