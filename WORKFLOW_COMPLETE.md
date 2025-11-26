# Complete Workflow - Multi-Agent System with Router

## 📊 Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          USER REQUEST                                      │
│                     (Chat or File Upload)                                  │
└────────────────────────────────┬───────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Endpoint                                  │
│                       (src/api/api.py)                                     │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  POST /chat  OR  POST /upload                                    │    │
│  │  Header: user-id                                                 │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬───────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                   get_orchestrator(user_id)                                │
│                   (src/orchestrator/orchestrator.py)                       │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  Global Registry: _orchestrators[user_id]                        │    │
│  │  • Check if orchestrator exists for this user                    │    │
│  │  • If not: Create new Orchestrator(user_id)                      │    │
│  │  • Call orchestrator.initialize()                                │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬───────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                    Orchestrator.__init__(user_id)                          │
│                    (src/orchestrator/orchestrator.py)                      │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  1. self.user_id = user_id                                       │    │
│  │  2. self.session_manager = session_manager (Redis)               │    │
│  │  3. self.faiss_service = FAISSService(user_id)                   │    │
│  │  4. self.file_parser = FileParserTool()                          │    │
│  │  5. self.agents = {} (empty dict)                                │    │
│  │  6. self.adk_session_service = InMemorySessionService()          │    │
│  │  7. self.adk_artifact_service = InMemoryArtifactService()        │    │
│  │  8. self.router_agent = None (will create in initialize)         │    │
│  │  9. self.router_runner = None                                    │    │
│  │  10. self.router_session_id = None                               │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬───────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                    Orchestrator.initialize()                               │
│                    (src/orchestrator/orchestrator.py)                      │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  STEP 1: Create Redis Session                                    │    │
│  │  └─> session_manager.create_session(user_id)                     │    │
│  │                                                                   │    │
│  │  STEP 2: Register TestCaseAgent                                  │    │
│  │  └─> test_case_agent = TestCaseAgent(user_id, ...)       ◄──┐   │    │
│  │      self.agents["test_case_agent"] = test_case_agent        │   │    │
│  │                                                              │   │    │
│  │  STEP 3: Register WeatherAgent                              │   │    │
│  │  └─> weather_agent = WeatherAgent(user_id, ...)        ◄────┼──┐│    │
│  │      self.agents["weather_agent"] = weather_agent           │  ││    │
│  │                                                              │  ││    │
│  │  STEP 4: Register TimeAgent                                 │  ││    │
│  │  └─> time_agent = TimeAgent(user_id, ...)              ◄────┼──┼┤    │
│  │      self.agents["time_agent"] = time_agent                 │  ││    │
│  │                                                              │  ││    │
│  │  STEP 5: Create Router Agent (LlmAgent)                     │  ││    │
│  │  └─> self.router_agent = LlmAgent(                          │  ││    │
│  │         model=LiteLlm(model="openai/gpt-4o-mini"),          │  ││    │
│  │         name="router_agent_xxx",                            │  ││    │
│  │         instruction="You are an intelligent router..."      │  ││    │
│  │      )                                                       │  ││    │
│  │                                                              │  ││    │
│  │  STEP 6: Create ADK Session for Router                      │  ││    │
│  │  └─> adk_session = adk_session_service.create_session(...)  │  ││    │
│  │      self.router_session_id = adk_session.id                │  ││    │
│  │                                                              │  ││    │
│  │  STEP 7: Create Runner for Router                           │  ││    │
│  │  └─> self.router_runner = Runner(                           │  ││    │
│  │         agent=self.router_agent,                            │  ││    │
│  │         session_service=adk_session_service,                │  ││    │
│  │         artifact_service=adk_artifact_service               │  ││    │
│  │      )                                                       │  ││    │
│  └──────────────────────────────────────────────────────────────┘  ││    │
└─────────────────────────────────────────────────────────────────────┼┼────┘
                                                                      ││
        ┌─────────────────────────────────────────────────────────────┘│
        │                                                              │
        │  ┌───────────────────────────────────────────────────────────┘
        │  │
        ▼  ▼  ▼
┌────────────────────────────────────────────────────────────────────────────┐
│              AGENT CREATION (happens 3 times in parallel)                  │
└────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────┐  ┌─────────────────────────────┐  ┌─────────────────────────────┐
│   TestCaseAgent.__init__    │  │   WeatherAgent.__init__     │  │   TimeAgent.__init__        │
│   (src/agents/              │  │   (src/agents/              │  │   (src/agents/              │
│    test_case_agent.py)      │  │    weather_agent.py)        │  │    time_agent.py)           │
├─────────────────────────────┤  ├─────────────────────────────┤  ├─────────────────────────────┤
│ 1. super().__init__(...)    │  │ 1. super().__init__(...)    │  │ 1. super().__init__(...)    │
│    [calls BaseAgent]        │  │    [calls BaseAgent]        │  │    [calls BaseAgent]        │
│                             │  │                             │  │                             │
│ 2. self.adk_agent =         │  │ 2. self.adk_agent =         │  │ 2. self.adk_agent =         │
│    self.create_adk_agent()◄─┤  │    self.create_adk_agent()◄─┤  │    self.create_adk_agent()◄─┤
│         │                   │  │         │                   │  │         │                   │
│         └───────┐           │  │         └───────┐           │  │         └───────┐           │
│                 ▼           │  │                 ▼           │  │                 ▼           │
│    ┌────────────────────┐  │  │    ┌────────────────────┐  │  │    ┌────────────────────┐  │
│    │ create_adk_agent() │  │  │    │ create_adk_agent() │  │  │    │ create_adk_agent() │  │
│    └────────────────────┘  │  │    └────────────────────┘  │  │    └────────────────────┘  │
│         │                   │  │         │                   │  │         │                   │
│         ▼                   │  │         ▼                   │  │         ▼                   │
│    LlmAgent(               │  │    LlmAgent(               │  │    LlmAgent(               │
│      model=LiteLlm(...),   │  │      model=LiteLlm(...),   │  │      model=LiteLlm(...),   │
│      name="test_case...",  │  │      name="weather...",    │  │      name="time...",       │
│      instruction="...",    │  │      instruction="...",    │  │      instruction="...",    │
│      tools=[]              │  │      tools=[get_weather]   │  │      tools=[get_current    │
│    )                       │  │    )                       │  │           _time]            │
│                             │  │                             │  │    )                       │
│ 3. self.adk_session_       │  │ 3. self.adk_session_       │  │ 3. self.adk_session_       │
│    service =               │  │    service =               │  │    service =               │
│    InMemorySessionService()│  │    InMemorySessionService()│  │    InMemorySessionService()│
│                             │  │                             │  │                             │
│ 4. self.adk_artifact_      │  │ 4. self.adk_artifact_      │  │ 4. self.adk_artifact_      │
│    service =               │  │    service =               │  │    service =               │
│    InMemoryArtifactService│  │    InMemoryArtifactService│  │    InMemoryArtifactService│
└─────────────────────────────┘  └─────────────────────────────┘  └─────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
                     INITIALIZATION COMPLETE
                     Orchestrator has 3 agents ready + Router
═══════════════════════════════════════════════════════════════════════════════

┌────────────────────────────────────────────────────────────────────────────┐
│                         USER SENDS CHAT MESSAGE                            │
│                    "What time is it in Israel?"                            │
└────────────────────────────────┬───────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│               Orchestrator.handle_chat(message)                            │
│               (src/orchestrator/orchestrator.py)                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  STEP 1: Route to correct agent                                  │    │
│  │  └─> agent_name = await self._route_to_agent(message)            │    │
│  │                          │                                        │    │
│  │                          ▼                                        │    │
│  │      ┌─────────────────────────────────────────────────┐         │    │
│  │      │  _route_to_agent(message)                       │         │    │
│  │      ├─────────────────────────────────────────────────┤         │    │
│  │      │  1. Prepare user_content (types.Content)        │         │    │
│  │      │  2. Run Router Agent:                           │         │    │
│  │      │     └─> router_runner.run_async(               │         │    │
│  │      │            user_id=self.user_id,               │         │    │
│  │      │            session_id=self.router_session_id,  │         │    │
│  │      │            new_message=user_content            │         │    │
│  │      │         )                                       │         │    │
│  │      │         │                                       │         │    │
│  │      │         ▼                                       │         │    │
│  │      │  ┌──────────────────────────────────────┐      │         │    │
│  │      │  │  Router Agent (LlmAgent)             │      │         │    │
│  │      │  │  - Analyzes: "time...Israel"         │      │         │    │
│  │      │  │  - Decision: "time_agent"            │      │         │    │
│  │      │  └──────────────────────────────────────┘      │         │    │
│  │      │         │                                       │         │    │
│  │      │         ▼                                       │         │    │
│  │      │  3. Extract agent name from response           │         │    │
│  │      │  4. Validate agent exists in self.agents       │         │    │
│  │      │  5. Return: "time_agent"                       │         │    │
│  │      └─────────────────────────────────────────────────┘         │    │
│  │                          │                                        │    │
│  │                          ▼                                        │    │
│  │  STEP 2: Get selected agent                                      │    │
│  │  └─> agent = self.agents.get("time_agent")                       │    │
│  │                                                                   │    │
│  │  STEP 3: Execute with selected agent                             │    │
│  │  └─> if agent_name == "test_case_agent":                         │    │
│  │         result = agent.process({"spec": message})                │    │
│  │      else:                                                        │    │
│  │         result = agent.process({"message": message}) ◄─────┐     │    │
│  │                                                            │     │    │
│  └────────────────────────────────────────────────────────────┼─────┘    │
└─────────────────────────────────────────────────────────────────┼──────────┘
                                                                  │
                                                                  ▼
┌────────────────────────────────────────────────────────────────────────────┐
│               TimeAgent.process({"message": "..."})                        │
│               (src/agents/time_agent.py)                                   │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  1. Extract message from input_data                              │    │
│  │  2. Create ADK session:                                          │    │
│  │     └─> session = adk_session_service.create_session(...)        │    │
│  │  3. Create Runner for this agent:                                │    │
│  │     └─> runner = Runner(                                         │    │
│  │            agent=self.adk_agent,  ◄─── (created in __init__)     │    │
│  │            session_service=adk_session_service,                  │    │
│  │            artifact_service=adk_artifact_service                 │    │
│  │         )                                                         │    │
│  │  4. Prepare user_content                                         │    │
│  │  5. Run agent:                                                   │    │
│  │     └─> async for event in runner.run_async(...):                │    │
│  │            │                                                      │    │
│  │            ▼                                                      │    │
│  │         ┌──────────────────────────────────────────┐             │    │
│  │         │  LlmAgent (TimeAgent)                    │             │    │
│  │         │  - Model: OpenAI gpt-4o-mini via LiteLlm│             │    │
│  │         │  - Instruction: "You are a time assist..."│             │    │
│  │         │  - Tool: get_current_time(location)      │             │    │
│  │         │                                          │             │    │
│  │         │  Agent analyzes message                  │             │    │
│  │         │  Decides to call tool: get_current_time  │             │    │
│  │         │  Calls: get_current_time("Israel")       │             │    │
│  │         │         │                                │             │    │
│  │         │         ▼                                │             │    │
│  │         │  ┌──────────────────────────────────┐   │             │    │
│  │         │  │  Function: get_current_time()    │   │             │    │
│  │         │  │  (defined in create_adk_agent)   │   │             │    │
│  │         │  ├──────────────────────────────────┤   │             │    │
│  │         │  │  1. Get current UTC time         │   │             │    │
│  │         │  │  2. Add offset for Israel (+2)   │   │             │    │
│  │         │  │  3. Format time string           │   │             │    │
│  │         │  │  4. Return: "Current time in     │   │             │    │
│  │         │  │     Israel: 09:45 PM on..."      │   │             │    │
│  │         │  └──────────────────────────────────┘   │             │    │
│  │         │         │                                │             │    │
│  │         │         ▼                                │             │    │
│  │         │  Agent formats final response            │             │    │
│  │         │  Returns: "The current time in Israel..."│             │    │
│  │         └──────────────────────────────────────────┘             │    │
│  │            │                                                      │    │
│  │            ▼                                                      │    │
│  │  6. Collect response text from events                            │    │
│  │  7. Return: {"response": "...", "error": False}                  │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬───────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│               Back to Orchestrator.handle_chat()                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  STEP 4: Format and return response                              │    │
│  │  └─> return {                                                     │    │
│  │         "response": result.get("response"),                       │    │
│  │         "agent_used": "time_agent",                               │    │
│  │         "test_cases": [],                                         │    │
│  │         "total_count": 0,                                         │    │
│  │         "coverage_areas": [],                                     │    │
│  │         "source": "orchestrator_routing"                          │    │
│  │      }                                                            │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬───────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                      FastAPI Returns to User                               │
│  {                                                                         │
│    "response": "The current time in Israel is 09:45 PM on...",           │
│    "agent_used": "time_agent"                                             │
│  }                                                                         │
└────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════

## 🔑 Key Points

### Where is `create_adk_agent()` called?

**Called 3 times during initialization:**

1. **TestCaseAgent.__init__()** (line ~53 in test_case_agent.py)
   ```python
   self.adk_agent = self.create_adk_agent()
   ```

2. **WeatherAgent.__init__()** (line ~40 in weather_agent.py)
   ```python
   self.adk_agent = self.create_adk_agent()
   ```

3. **TimeAgent.__init__()** (line ~40 in time_agent.py)
   ```python
   self.adk_agent = self.create_adk_agent()
   ```

**When is it called in the flow?**
- During `Orchestrator.initialize()`
- When each agent is instantiated
- BEFORE the orchestrator is ready to handle requests
- Happens ONCE per agent per user

### Agent Creation Sequence

```
Orchestrator.initialize()
  ├─> TestCaseAgent(user_id, ...)
  │     ├─> super().__init__(...)
  │     ├─> self.adk_agent = self.create_adk_agent()  ◄── HERE!
  │     │      └─> Returns: LlmAgent(model, name, instruction, tools=[])
  │     ├─> self.adk_session_service = InMemorySessionService()
  │     └─> self.adk_artifact_service = InMemoryArtifactService()
  │
  ├─> WeatherAgent(user_id, ...)
  │     ├─> super().__init__(...)
  │     ├─> self.adk_agent = self.create_adk_agent()  ◄── HERE!
  │     │      └─> Returns: LlmAgent(model, name, instruction, tools=[get_weather])
  │     ├─> self.adk_session_service = InMemorySessionService()
  │     └─> self.adk_artifact_service = InMemoryArtifactService()
  │
  └─> TimeAgent(user_id, ...)
        ├─> super().__init__(...)
        ├─> self.adk_agent = self.create_adk_agent()  ◄── HERE!
        │      └─> Returns: LlmAgent(model, name, instruction, tools=[get_current_time])
        ├─> self.adk_session_service = InMemorySessionService()
        └─> self.adk_artifact_service = InMemoryArtifactService()
```

### Routing Decision Tree

```
User Message → Router Agent (LlmAgent) analyzes
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   "test case"    "weather"      "time"
   "generate"     "temperature"  "clock"
   "specification" "climate"     "timezone"
        │              │              │
        ▼              ▼              ▼
  test_case_agent  weather_agent  time_agent
        │              │              │
        └──────────────┴──────────────┘
                       │
                       ▼
           Orchestrator.handle_chat()
           executes selected agent
```

---

**Generated**: 2025-11-25
**Branch**: new_version_adk_check_routing_orchestrator
