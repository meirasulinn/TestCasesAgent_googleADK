# Why Your Current Code Fails - Detailed Analysis

## Current Code Issues

Your current implementation in `src/agents/test_case_agent.py` has several fundamental misunderstandings about how Google ADK works:

```python
# CURRENT (WRONG) CODE:
from google.adk import Agent, Runner

class TestCaseAgent(Agent):  # ❌ Problem 1: Subclassing Agent
    def __init__(self, name):
        super().__init__(name)  # ❌ Problem 2: Wrong init signature

    def execute(self, input_data):  # ❌ Problem 3: execute() doesn't exist
        # Logic for generating test cases
        print(f"Executing agent {self.name} with input: {input_data}")
        return {"status": "success", "test_cases": ["TestCase1", "TestCase2"]}

class TestCaseRunner(Runner):  # ❌ Problem 4: Subclassing Runner
    def __init__(self):
        super().__init__()  # ❌ Problem 5: Wrong init signature
        self.agents = []

    def register_agent(self, agent):
        self.agents.append(agent)

    def run(self, input_data):  # ❌ Problem 6: Wrong signature
        results = []
        for agent in self.agents:
            result = agent.execute(input_data)  # ❌ Problem 7: execute() doesn't exist
            results.append(result)
        return results
```

---

## Issue-by-Issue Breakdown

### ❌ Problem 1: Subclassing Agent (LlmAgent)

```python
class TestCaseAgent(Agent):
    pass
```

**Why this is wrong:**
- Agent (LlmAgent) is a **configuration object**, not meant to be subclassed
- It's a Pydantic BaseModel, not a traditional class to extend
- All agent behavior is defined through **field configuration**, not inheritance

**What you should do instead:**

```python
from google.adk import Agent

# Create an instance, don't subclass
agent = Agent(
    name="test_case_generator",
    model="gemini-2.0-flash",
    instruction="Generate test cases...",
)
```

---

### ❌ Problem 2: Wrong Agent Constructor Signature

```python
class TestCaseAgent(Agent):
    def __init__(self, name):
        super().__init__(name)  # ❌ Agent.__init__ doesn't take just 'name'
```

**What Agent actually requires:**

```python
# Agent requires keyword arguments, not positional
Agent(
    name="test_case_generator",  # REQUIRED
    model="gemini-2.0-flash",     # REQUIRED (or inherited from parent)
    instruction="...",             # OPTIONAL
    tools=[],                       # OPTIONAL
    # ... and many other optional fields
)

# NOT:
Agent("test_case_generator")  # This will fail
```

---

### ❌ Problem 3: `.execute()` Method Doesn't Exist

```python
def execute(self, input_data):
    return {"status": "success"}

# Later:
result = agent.execute(input_data)  # ❌ AttributeError: Agent has no method 'execute'
```

**What actually exists:**

```python
# The ONLY execution methods on BaseAgent are:
async def run_async(self, parent_context: InvocationContext) -> AsyncGenerator[Event, None]:
    """Execute agent via text conversation."""
    pass

async def run_live(self, parent_context: InvocationContext) -> AsyncGenerator[Event, None]:
    """Execute agent via audio/video."""
    pass

# And these are for INTERNAL use by Runner, not direct calling
```

**You cannot call agent.run_async() directly.** You must use `Runner.run_async()`:

```python
# ❌ WRONG:
async for event in agent.run_async(context):
    pass

# ✓ CORRECT:
async for event in runner.run_async(
    user_id="user123",
    session_id="session456",
    new_message=user_message,
):
    pass
```

---

### ❌ Problem 4: Subclassing Runner

```python
class TestCaseRunner(Runner):
    def __init__(self):
        super().__init__()  # ❌ Runner.__init__ has required parameters
        self.agents = []

    def run(self, input_data):
        # Custom logic
        pass
```

**Why this is wrong:**
- Runner is not meant to be subclassed - it's a complete implementation
- Runner already handles all orchestration, event management, session handling
- Adding custom logic via subclassing breaks the framework

**What Runner's constructor actually requires:**

```python
Runner(
    app_name="my_app",                    # REQUIRED (if app not provided)
    agent=my_agent,                       # REQUIRED (if app not provided)
    session_service=session_service,      # REQUIRED
    artifact_service=artifact_service,    # OPTIONAL
    memory_service=memory_service,        # OPTIONAL
)

# NOT:
class MyRunner(Runner):
    def __init__(self):
        super().__init__()  # ❌ Missing required parameters
```

---

### ❌ Problem 5: Wrong Runner Constructor

```python
class TestCaseRunner(Runner):
    def __init__(self):
        super().__init__()  # ❌ Missing required arguments
```

**Runner.__init__ signature:**

```python
def __init__(
    self,
    *,
    app: Optional[App] = None,
    app_name: Optional[str] = None,              # Required if app not provided
    agent: Optional[BaseAgent] = None,           # Required if app not provided
    plugins: Optional[List[BasePlugin]] = None,  # Deprecated
    artifact_service: Optional[BaseArtifactService] = None,
    session_service: BaseSessionService,         # ALWAYS REQUIRED
    memory_service: Optional[BaseMemoryService] = None,
    credential_service: Optional[BaseCredentialService] = None,
):
```

All parameters are keyword-only (notice the `*`). You must call it like:

```python
runner = Runner(
    app_name="my_app",
    agent=agent,
    session_service=InMemorySessionService(),
)
```

---

### ❌ Problem 6: Wrong `.run()` Signature

```python
def run(self, input_data):
    results = []
    for agent in self.agents:
        result = agent.execute(input_data)
        results.append(result)
    return results
```

**Runner.run() actual signature:**

```python
def run(
    self,
    *,
    user_id: str,                              # User identifier
    session_id: str,                           # Session identifier
    new_message: types.Content,                # User message
    run_config: Optional[RunConfig] = None,    # Optional config
) -> Generator[Event, None, None]:
    """Synchronous wrapper for testing (uses background thread)."""
    pass

# Returns Generator of Events, not final result
```

And there's also the **async** version (recommended for production):

```python
async def run_async(
    self,
    *,
    user_id: str,
    session_id: str,
    invocation_id: Optional[str] = None,
    new_message: Optional[types.Content] = None,
    state_delta: Optional[dict[str, Any]] = None,
    run_config: Optional[RunConfig] = None,
) -> AsyncGenerator[Event, None]:
    """Production method - async generator."""
    pass
```

---

### ❌ Problem 7: Calling Non-Existent `.execute()` Method

```python
for agent in self.agents:
    result = agent.execute(input_data)  # ❌ Agent has NO execute() method
```

**Actual invocation pattern:**

```python
# Step 1: Create session (required!)
session = await session_service.get_session(
    app_name="my_app",
    user_id="user123",
    session_id="session456",
)

# Step 2: Prepare message
from google.genai import types
message = types.Content(role='user', parts=[types.Part(text="Your prompt")])

# Step 3: Run through Runner (not agent)
async for event in runner.run_async(
    user_id="user123",
    session_id="session456",
    new_message=message,
):
    # Process each event
    print(event.content)
```

---

## Additional Misunderstandings

### Misunderstanding 1: Synchronous Execution

Your code assumes everything is synchronous:

```python
result = agent.execute(input_data)  # Expect immediate result
```

**Reality: Everything is async**

```python
# MUST be async - there's no sync path
async for event in runner.run_async(...):
    # Process events
    pass

# Can fake sync for testing with run():
for event in runner.run(...):  # Uses background thread
    pass
```

---

### Misunderstanding 2: Direct Agent Invocation

Your code calls agent methods directly:

```python
agent.execute(input_data)
```

**Reality: Agents run ONLY through Runner**

```python
# ❌ Agent has no execution methods you can call:
agent.execute()        # ❌ Doesn't exist
agent.run()            # ❌ Doesn't exist  
agent.run_async()      # ✓ Exists but NOT for external use (InvocationContext required)

# ✓ Use Runner instead:
runner.run()           # ✓ Sync wrapper for testing
runner.run_async()     # ✓ Async for production
```

---

### Misunderstanding 3: State Management

Your code doesn't handle sessions/state:

```python
result = agent.execute(input_data)  # No session?
```

**Reality: Agents operate within Sessions**

```python
# Sessions store:
# - Conversation history
# - State variables
# - Artifacts
# - User/app context

session = await session_service.get_session(
    app_name="my_app",
    user_id="user123",
    session_id="session456",
)

# Agent reads/writes session.state during execution
# Results are retrieved from session.state afterward
```

---

### Misunderstanding 4: Structured Input/Output

Your code returns hardcoded results:

```python
return {"status": "success", "test_cases": ["TestCase1", "TestCase2"]}
```

**Reality: Use Pydantic schemas for structured I/O**

```python
from pydantic import BaseModel

class TestCaseInput(BaseModel):
    spec_file: str
    num_cases: int

class TestCaseOutput(BaseModel):
    test_cases: list[dict]
    total_count: int

agent = Agent(
    name="generator",
    input_schema=TestCaseInput,    # Validates incoming data
    output_schema=TestCaseOutput,  # Validates LLM response
    output_key="results",          # Stores in session.state["results"]
)

# Later, after run_async():
session = await session_service.get_session(...)
results = session.state["results"]  # Typed as TestCaseOutput
```

---

### Misunderstanding 5: Agent Tree Registration

Your code uses manual registration:

```python
class TestCaseRunner(Runner):
    def register_agent(self, agent):
        self.agents.append(agent)

orchestrator.register_agent(agent1)
orchestrator.register_agent(agent2)
```

**Reality: Agents form a tree structure**

```python
# Define sub-agents:
child_agent_1 = Agent(name="generator_1", ...)
child_agent_2 = Agent(name="generator_2", ...)

# Add to parent agent
root_agent = Agent(
    name="root",
    sub_agents=[child_agent_1, child_agent_2],
)

# Runner gets the root
runner = Runner(app_name="...", agent=root_agent, ...)
```

---

## The Correct Patterns

### Pattern 1: Basic Agent Execution

```python
import asyncio
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types

async def run_agent():
    # 1. Create agent (don't subclass!)
    agent = Agent(
        name="my_agent",
        model="gemini-2.0-flash",
        instruction="You are helpful.",
    )
    
    # 2. Setup services
    session_service = InMemorySessionService()
    
    # 3. Create session (required!)
    session = Session(app_name="app", user_id="user1", id="session1")
    await session_service.save_session(session)
    
    # 4. Create runner (don't subclass!)
    runner = Runner(
        app_name="app",
        agent=agent,
        session_service=session_service,
    )
    
    # 5. Execute via runner (not agent!)
    message = types.Content(role='user', parts=[types.Part(text="Hello")])
    async for event in runner.run_async(
        user_id="user1",
        session_id="session1",
        new_message=message,
    ):
        if event.is_final_response():
            print("Agent says:", event.content)

asyncio.run(run_agent())
```

### Pattern 2: With Input/Output Schemas

```python
from pydantic import BaseModel

class Input(BaseModel):
    query: str

class Output(BaseModel):
    result: str
    confidence: float

agent = Agent(
    name="analyzer",
    model="gemini-2.0-flash",
    input_schema=Input,
    output_schema=Output,
    output_key="analysis_result",
    instruction="Analyze the input.",
)

# After run_async() completes:
session = await session_service.get_session(...)
result: Output = session.state["analysis_result"]
```

### Pattern 3: With Sub-agents

```python
sub_agent_1 = Agent(name="generator", ...)
sub_agent_2 = Agent(name="validator", ...)

root_agent = Agent(
    name="root",
    model="gemini-2.0-flash",
    sub_agents=[sub_agent_1, sub_agent_2],
    instruction="Use sub-agents as needed.",
)

runner = Runner(app_name="app", agent=root_agent, ...)
```

---

## Summary of Changes Needed

| Current (Wrong) | Should Be (Correct) |
|---|---|
| `class TestCaseAgent(Agent):` | `agent = Agent(name="...", ...)` |
| `def execute(self, input_data):` | `async for event in runner.run_async(...)` |
| `class TestCaseRunner(Runner):` | `runner = Runner(app_name="...", agent=agent, ...)` |
| `agent.execute()` | Retrieve from `session.state` |
| Direct agent calls | Always through `runner.run_async()` |
| No session handling | Create session before running |
| Hardcoded results | Use `input_schema` / `output_schema` |
| Manual agent registration | Define `sub_agents` list |

---

## Error Messages You'll See

If you try to run your current code:

```
# Error 1: execute() doesn't exist
AttributeError: 'LlmAgent' object has no attribute 'execute'

# Error 2: Wrong Agent init
TypeError: __init__() missing required keyword-only arguments: 'model'

# Error 3: Runner init missing session_service
TypeError: __init__() missing required keyword-only argument: 'session_service'

# Error 4: Runner not properly initialized
RuntimeError: Runner not properly initialized, session_service is None
```

---

## References

- **LlmAgent class**: `venv/Lib/site-packages/google/adk/agents/llm_agent.py` (lines 1-917)
- **Runner class**: `venv/Lib/site-packages/google/adk/runners.py` (lines 1-1365)
- **BaseAgent class**: `venv/Lib/site-packages/google/adk/agents/base_agent.py` (lines 1-659)
- **Event class**: `venv/Lib/site-packages/google/adk/events/event.py`
- **Session class**: `venv/Lib/site-packages/google/adk/sessions/session.py`
