# Architecture Documentation - Generic Agent Framework

## 🏗️ System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                       USER REQUEST                               │
│                    (HTTP with user-id header)                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
                ┌────────────────────┐
                │   FastAPI Router   │
                │   (src/api/api.py) │
                └────────┬───────────┘
                         │
                         ▼
          ┌──────────────────────────────┐
          │  get_orchestrator(user_id)   │
          │  • Check registry            │
          │  • Create if not exists      │
          │  • Return Orchestrator       │
          └──────────┬───────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│               ORCHESTRATOR (Per-User Instance)                   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 1. Router Agent (LlmAgent)                               │  │
│  │    • Analyzes user message                               │  │
│  │    • Returns agent name (e.g., "time_agent")            │  │
│  └──────────────┬───────────────────────────────────────────┘  │
│                 │                                                │
│                 ▼                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 2. Agent Selection                                       │  │
│  │    • Get agent from registry                             │  │
│  │    • Validate agent exists                               │  │
│  └──────────────┬───────────────────────────────────────────┘  │
│                 │                                                │
│                 ▼                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 3. Agent Execution                                       │  │
│  │    • Call agent.process(input)                           │  │
│  │    • Agent uses ADK LlmAgent with tools                  │  │
│  └──────────────┬───────────────────────────────────────────┘  │
└─────────────────┼────────────────────────────────────────────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │   RESPONSE (JSON)   │
        │   • response        │
        │   • agent_used      │
        │   • source          │
        └─────────────────────┘
```

---

## 📦 Component Breakdown

### 1. API Layer (`src/api/api.py`)

**Responsibility:** HTTP interface and request handling

**Endpoints:**
- `POST /chat` - Main chat endpoint with routing
- `GET /health` - Health check
- `GET /session/{user_id}` - Get user session

**Key Features:**
- FastAPI with Pydantic validation
- User-ID header for multi-user support
- Error handling and logging
- Auto-generated OpenAPI docs

**Flow:**
```python
@app.post("/chat")
async def chat(request: ChatRequest, user_id: str):
    orchestrator = await get_orchestrator(user_id)
    result = await orchestrator.handle_chat(request.message)
    return ChatResponse(**result)
```

---

### 2. Orchestrator (`src/orchestrator/orchestrator.py`)

**Responsibility:** Coordinate agents and route requests

**Architecture:**
```
Orchestrator Instance (per user)
├── Router Agent (LlmAgent) - Decides which agent to use
├── Agent Registry - Dict of available agents
├── Session Manager - Redis access
└── FAISS Service - Optional semantic search
```

**Key Methods:**

1. **`initialize()`**
   - Create Redis session
   - Register agents
   - Create router agent
   - Setup ADK runners

2. **`handle_chat(message)`**
   - Route to appropriate agent
   - Execute agent
   - Return response

3. **`_route_to_agent(message)`**
   - Use router LlmAgent
   - Analyze message
   - Return agent name

**Global Registry:**
```python
_orchestrators: Dict[str, Orchestrator] = {}

async def get_orchestrator(user_id: str) -> Orchestrator:
    if user_id not in _orchestrators:
        orchestrator = Orchestrator(user_id)
        await orchestrator.initialize()
        _orchestrators[user_id] = orchestrator
    return _orchestrators[user_id]
```

---

### 3. Router Agent (Google ADK LlmAgent)

**Responsibility:** Intelligent request routing

**How It Works:**
```
User Message → Router Agent (LlmAgent)
                    ↓
            Analyze message semantically
                    ↓
            Match to agent description
                    ↓
            Return agent name only
```

**Router Instruction Template:**
```
You are an intelligent router for a multi-agent system.

Available agents:
- time_agent: Provides current time for timezones
- weather_agent: Provides weather information
- your_agent: Does XYZ tasks

Your job:
1. Analyze the user's request
2. Determine which agent should handle it
3. Respond ONLY with the agent name

Rules:
- If about time → "time_agent"
- If about weather → "weather_agent"
- If about XYZ → "your_agent"
- Respond with ONLY the agent name
```

**Why LlmAgent for Routing?**
- ✅ Semantic understanding (not keyword matching)
- ✅ Handles ambiguous requests
- ✅ Adapts to natural language variations
- ✅ No hardcoded if/else logic

---

### 4. Base Agent (`src/agents/base_agent.py`)

**Responsibility:** Abstract base class for all agents

**Contract:**
```python
class BaseAgent(ABC):
    def __init__(self, name, user_id, session_manager, faiss_service):
        # Initialize agent
        
    @abstractmethod
    def create_adk_agent(self) -> LlmAgent:
        # Create Google ADK LlmAgent with tools
        
    @abstractmethod
    async def process(self, input_data: Dict) -> Dict:
        # Process request and return response
```

**What Agents Get:**
- `self.name` - Agent name
- `self.user_id` - Current user
- `self.session_manager` - Redis access
- `self.faiss_service` - Semantic search (optional)

---

### 5. Specialized Agents (Examples)

#### TimeAgent (`src/agents/time_agent.py`)

**Tool:** `get_current_time(location: str)`

**Flow:**
```
User: "What time is it in New York?"
  ↓
Router: "time_agent"
  ↓
TimeAgent.process()
  ├─> Create ADK session
  ├─> Create Runner
  ├─> Run LlmAgent with tool
  │   ├─> LlmAgent analyzes message
  │   ├─> Decides to call get_current_time("New York")
  │   ├─> Tool executes → returns time string
  │   └─> LlmAgent formats response
  └─> Return response
```

**Key Code:**
```python
def get_current_time(location: str = "UTC") -> str:
    """Get current time for location."""
    now = datetime.now(timezone.utc)
    offset = timezone_offsets.get(location.lower(), 0)
    local_time = now + timedelta(hours=offset)
    return f"Current time in {location}: {local_time}..."

agent = LlmAgent(
    model=LiteLlm(model=settings.OPENAI_MODEL),
    tools=[get_current_time]  # ADK auto-converts
)
```

#### WeatherAgent (`src/agents/weather_agent.py`)

**Tool:** `get_weather(city: str)`

**Similar flow to TimeAgent but with weather data**

---

### 6. Session Manager (`src/services/session_manager.py`)

**Responsibility:** Redis-based persistent storage

**Redis Key Structure:**
```
session:{user_id} → {
    "user_id": "alice",
    "files": [],
    "history": [],
    "state": {}
}

cache:{key} → {
    "data": "...",
    TTL: 3600
}
```

**Key Methods:**
- `create_session(user_id)` - Create new session
- `get_session(user_id)` - Get session data
- `update_session(user_id, data)` - Update session
- `get_cache(key)` - Get cached data
- `set_cache(key, value, ttl)` - Cache with TTL

**Why Redis?**
- ✅ Fast in-memory storage
- ✅ Persistent across restarts
- ✅ TTL support for expiration
- ✅ Shared across server instances

---

### 7. FAISS Service (`src/services/faiss_service.py`) - OPTIONAL

**Responsibility:** Semantic search with embeddings

**Architecture:**
```
FAISSService (per user)
├── FAISS Index - Vector database (1536 dimensions)
├── Documents - Original text
└── Metadata - Associated data
```

**Flow:**
```
Add Document:
Text → OpenAI Embedding API → Vector (1536D) → FAISS Index

Search:
Query → OpenAI Embedding API → Query Vector → FAISS.search()
  → Top-K similar docs → Filter by threshold → Return results
```

**Use Cases:**
- Find similar previous requests
- Deduplicate content
- Smart caching
- Context retrieval

**Note:** Can be removed if not needed!

---

## 🔄 Complete Request Flow

### Example: "What time is it in Israel?"

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. HTTP Request                                                  │
│    POST /chat                                                    │
│    Headers: user-id: alice                                       │
│    Body: {"message": "What time is it in Israel?"}              │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. API Handler (api.py)                                          │
│    • Validate request                                            │
│    • Extract user_id from header                                 │
│    • Get orchestrator for user                                   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Get/Create Orchestrator                                       │
│    • Check _orchestrators["alice"]                               │
│    • If exists → return                                          │
│    • If not → create, initialize, register                       │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Orchestrator.handle_chat()                                    │
│    • Call _route_to_agent(message)                               │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Router Agent Execution                                        │
│    • Router LlmAgent receives: "What time is it in Israel?"     │
│    • Analyzes: mentions "time" + "Israel"                        │
│    • Matches instruction: "If about time → time_agent"          │
│    • Returns: "time_agent"                                       │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. Agent Selection                                               │
│    • Get agent from registry: agents["time_agent"]               │
│    • Validate agent exists                                       │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. TimeAgent.process()                                           │
│    • Create ADK session for this request                         │
│    • Create Runner with TimeAgent's LlmAgent                     │
│    • Run agent with message                                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. TimeAgent's LlmAgent Execution                                │
│    • Receives: "What time is it in Israel?"                     │
│    • Understands: Need to get time for Israel                   │
│    • Decides: Call get_current_time("Israel")                    │
│    • Tool executes:                                              │
│      - Get UTC time                                              │
│      - Add Israel offset (+2)                                    │
│      - Format result                                             │
│    • Returns: "Current time in Israel: 09:45 PM on..."          │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. Response Assembly                                             │
│    {                                                             │
│      "response": "Current time in Israel: 09:45 PM...",         │
│      "agent_used": "time_agent",                                 │
│      "source": "orchestrator_routing"                            │
│    }                                                             │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 10. HTTP Response                                                │
│     Status: 200 OK                                               │
│     Body: JSON response                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔐 Multi-User Isolation

### How Isolation Works:

```
User Alice                           User Bob
    │                                    │
    ├─> Orchestrator("alice")            ├─> Orchestrator("bob")
    │   ├─> Redis: session:alice         │   ├─> Redis: session:bob
    │   ├─> FAISS: alice_instance        │   ├─> FAISS: bob_instance
    │   ├─> Router: router_alice         │   ├─> Router: router_bob
    │   └─> Agents: time, weather        │   └─> Agents: time, weather
    │                                    │
    └─> Isolated ✅                      └─> Isolated ✅
```

**Isolation Guarantees:**

1. **Orchestrator Level**
   - Each user gets separate Orchestrator instance
   - Stored in global registry: `_orchestrators[user_id]`

2. **Redis Level**
   - Sessions keyed by user: `session:{user_id}`
   - No cross-user access possible

3. **FAISS Level**
   - Separate FAISS instance per user
   - Alice's vectors ≠ Bob's vectors

4. **ADK Session Level**
   - Each agent execution creates new session
   - Ephemeral, per-request

**Shared Components:**
- ❌ Session data (isolated)
- ❌ FAISS indexes (isolated)
- ✅ Agent code (shared, stateless)
- ✅ Redis connection (shared pool)

---

## 📊 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA STORAGE LAYERS                       │
└─────────────────────────────────────────────────────────────┘

Layer 1: HTTP Request
    ├─ Headers: user-id
    └─ Body: message

Layer 2: In-Memory (Python Process)
    ├─ Orchestrator Registry: Dict[user_id, Orchestrator]
    ├─ FAISS Indexes: Per-user instances
    └─ ADK Sessions: InMemorySessionService (ephemeral)

Layer 3: Redis (Persistent)
    ├─ session:{user_id} → User session data
    └─ cache:{key} → Cached results (optional)

Layer 4: External APIs
    ├─ OpenAI API: LLM calls + embeddings
    └─ (Your external services)
```

---

## 🛠️ Extension Points

### 1. Add New Agent

**Location:** `src/agents/your_agent.py`

**Steps:**
1. Inherit from `BaseAgent`
2. Implement `create_adk_agent()` with tools
3. Implement `process()` method
4. Register in `orchestrator.py`
5. Update router instruction

### 2. Add Custom Tool

**In agent's `create_adk_agent()`:**
```python
def your_tool(param: str) -> dict:
    """Tool description."""
    # Your logic
    return result

agent = LlmAgent(
    tools=[your_tool]  # ADK auto-converts
)
```

### 3. Add Caching

**In agent's `process()`:**
```python
# Check cache
cached = await self.session_manager.get_cache(cache_key)
if cached:
    return cached

# Generate result
result = await expensive_operation()

# Cache it
await self.session_manager.set_cache(cache_key, result, ttl=3600)
return result
```

### 4. Add FAISS Search

**In agent's `process()`:**
```python
# Search for similar documents
similar = await self.faiss_service.search(query, top_k=3)

# Use similar docs as context
context = "\n".join([doc["document"] for doc in similar])
```

---

## 🎯 Design Principles

1. **Single Responsibility**
   - Each agent handles one domain
   - Router only routes
   - Orchestrator only coordinates

2. **Dependency Injection**
   - Agents receive dependencies (session_manager, faiss)
   - Easy to test and mock

3. **Stateless Agents**
   - Agents don't store state
   - All state in Redis or passed as parameters

4. **Per-User Isolation**
   - Each user gets separate orchestrator
   - No cross-contamination

5. **Extensibility**
   - Easy to add new agents
   - Clear extension points
   - No modification of core code

6. **Configuration over Code**
   - Settings in .env
   - Router instruction in one place
   - Easy to customize

---

**Built with ❤️ using Google ADK + OpenAI**
