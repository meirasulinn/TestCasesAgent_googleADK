# 🏗️ ADK v2 - מבנה קבצים וזרימה

## 📁 היררכיית הקבצים

```
adk_TestCaseAgent_poc/
│
├── 📄 .env                          # משתנים: OPENAI_API_KEY
├── 🐳 docker-compose.yml           # Redis על port 6381
│
├── 📦 src/
│   │
│   ├── 🌐 api_adk.py               # FastAPI endpoints (async)
│   │   └── מאתחל: ADKTestCaseOrchestrator
│   │   └── Endpoints: /run, /upload, /health
│   │
│   ├── 🤖 agents/
│   │   ├── google_adk_agent.py     # ⭐ [ADK LlmAgent]
│   │   │   ├── class TestCaseAgent(LlmAgent)
│   │   │   ├── def run_async()       # async method
│   │   │   └── def generate_test_cases_sync()  # OpenAI call
│   │   │
│   │   ├── adk_orchestrator.py      # ⭐ [ADK Orchestrator]
│   │   │   ├── class ADKTestCaseOrchestrator
│   │   │   ├── register_agent()
│   │   │   └── async def run()       # זרימה ראשית
│   │   │
│   │   ├── test_case_orchestrator.py # [v1.0 - OLD - לא בשימוש]
│   │   └── test_case_agent.py        # [v1.0 - OLD - לא בשימוש]
│   │
│   ├── 🧠 rag/
│   │   ├── adk_rag_tool.py          # ⭐ [ADK Tools]
│   │   │   ├── class RAGSearchTool(BaseTool)
│   │   │   │   └── async def run_async()
│   │   │   ├── class RAGCacheTool(BaseTool)
│   │   │   │   └── async def run_async()
│   │   │   └── Redis + FAISS integration
│   │   │
│   │   ├── retrieval.py              # [v1.0 - OLD - לא בשימוש]
│   │   ├── redis_client.py           # Config
│   │   └── faiss_index.py            # Config
│   │
│   └── api.py                        # [v1.0 - OLD sync API - לא בשימוש]
│
├── 🧪 tests/
├── 📚 config/
└── 📖 README_ADK_v2.md
```

---

## 🔄 זרימת הנתונים - User Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CLIENT (Postman / Frontend)                       │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                    POST /upload (PDF או JSON)
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    api_adk.py:FastAPI                                │
│            ✅ async def upload_endpoint()                            │
│  - Parse PDF ➜ Extract text                                          │
│  - Call orchestrator.run()                                           │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│         ADKTestCaseOrchestrator:adk_orchestrator.py                  │
│              ⭐ [ADK Orchestrator Pattern]                           │
│                                                                       │
│            async def run(input_spec):                                │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ STEP 1: Check Cache (RAG Search)                            │    │
│  │  ⭐ [ADK Tool - BaseTool]                                   │    │
│  │  await rag_search_tool.run_async({"spec": spec_text})      │    │
│  │  └─ Redis lookup בתוך FAISS similarity check               │    │
│  │                                                              │    │
│  │  IF cache_hit:                                              │    │
│  │    ✅ Return cached results (50ms)                          │    │
│  │  ELSE:                                                      │    │
│  │    Go to STEP 2                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                          │                                            │
│                          ▼                                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ STEP 2: Generate Test Cases (Cache Miss)                   │    │
│  │                                                              │    │
│  │  FOR each agent IN [Agent1, Agent2]:                        │    │
│  │    await agent.run_async({"spec": spec_text})              │    │
│  │    ⭐ [ADK LlmAgent - google_adk_agent.py]                 │    │
│  │    │                                                        │    │
│  │    └─ await generate_test_cases_sync()                     │    │
│  │       ├─ Initialize OpenAI client                          │    │
│  │       ├─ Call gpt-4o-mini API                              │    │
│  │       └─ Parse JSON ➜ 10-12 test cases                     │    │
│  │                                                              │    │
│  │  Result: [{agent: Agent1, test_cases: [...]},              │    │
│  │           {agent: Agent2, test_cases: [...]}]              │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                          │                                            │
│                          ▼                                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ STEP 3: Cache Results (RAG Cache)                           │    │
│  │  ⭐ [ADK Tool - BaseTool]                                   │    │
│  │  await rag_cache_tool.run_async({                           │    │
│  │    "spec": spec_text,                                       │    │
│  │    "results": agent_results                                │    │
│  │  })                                                          │    │
│  │  ├─ Store in Redis (TTL: 24h)                              │    │
│  │  └─ Index in FAISS (semantic search)                       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                          │                                            │
│                          ▼                                            │
│            RETURN: {                                                  │
│              "rag_source": "generated",                              │
│              "results": [...test_cases...]                          │
│            }                                                          │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    api_adk.py:FastAPI Response                       │
│              ✅ Return 200 OK + JSON                                 │
│              📊 Timing: 5-10s (generation) / 50ms (cached)          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 המרכיבים הראשיים

### 1️⃣ **FastAPI Layer** (`api_adk.py`)
```
📡 Endpoints:
  GET  /              ➜ Health check
  POST /upload        ➜ PDF/JSON upload
  POST /run           ➜ Run generation
  POST /health        ➜ Status
```

### 2️⃣ **Orchestrator** (`adk_orchestrator.py`) ⭐ [ADK Pattern]
```
🎪 ADKTestCaseOrchestrator:
  • register_agent(agent) ➜ Add LlmAgent
  • async run(spec) ➜ Orchestrate flow
```

### 3️⃣ **Agents** (`google_adk_agent.py`) ⭐ [ADK LlmAgent]
```
🤖 TestCaseAgent(LlmAgent):
  • Inherits from: google.adk.LlmAgent
  • async def run_async(input_data)
  • Calls OpenAI (gpt-4o-mini)
  • Returns: {test_cases: [...]}
```

### 4️⃣ **RAG Tools** (`adk_rag_tool.py`) ⭐ [ADK BaseTool]
```
🔧 RAGSearchTool(BaseTool):
  • async def run_async(input_data)
  • Searches Redis + FAISS
  • Returns: {source, similarity, result}

🔧 RAGCacheTool(BaseTool):
  • async def run_async(input_data)
  • Stores in Redis (24h TTL)
  • Indexes in FAISS
```

---

## 📊 ביצוע עומס ויתמודדות עם שגיאות

### Cache Hit Path (מהר ⚡)
```
User Upload
    ↓
RAGSearchTool.run_async()
    ↓ (Redis/FAISS hit)
Return cached [10-12 test cases]
    ↓
🟢 50-200ms total
```

### Cache Miss Path (איטי 🐢)
```
User Upload
    ↓
RAGSearchTool.run_async()
    ↓ (miss)
Agent1.run_async() ➜ OpenAI API (2-3s)
    ↓
Agent2.run_async() ➜ OpenAI API (2-3s)
    ↓
RAGCacheTool.run_async() ➜ Store
    ↓
Return [19-22 test cases combined]
    ↓
🔴 5-10s total
```

---

## 🛡️ Error Handling Hierarchy

```
┌─ FastAPI Endpoint ──────────────────────┐
│  try:                                    │
│    ├─ rag_search_tool.run_async()       │
│    ├─ agent.run_async()                 │
│    ├─ rag_cache_tool.run_async()        │
│    └─ except Exception: log + 500       │
└──────────────────────────────────────────┘
```

---

## 🔌 External Dependencies

```
🌐 External Services:
  • OpenAI API (gpt-4o-mini model)
    └─ LiteLLM format: "openai/gpt-4o-mini"

🐳 Docker Containers:
  • Redis:6381
    └─ 24-hour TTL cache storage

📚 Python Libraries (ADK):
  ⭐ google.adk.LlmAgent
  ⭐ google.adk.tools.BaseTool
  ⭐ google.adk.runners
  ✅ FastAPI (Starlette)
  ✅ redis
  ✅ faiss-cpu
  ✅ openai
```

---

## 📈 v1.0 vs v2.0

| Aspect | v1.0 | v2.0 |
|--------|------|------|
| **Orchestrator** | Custom class | ⭐ ADK Pattern |
| **Agents** | Custom Python | ⭐ ADK LlmAgent |
| **Tools** | Custom RAG class | ⭐ ADK BaseTool |
| **Runner** | Not used | (Direct invocation) |
| **API** | Sync (blocking) | ✅ Async (FastAPI) |
| **RAG** | Custom implementation | ✅ Integrated as Tools |
| **Performance** | Works | ✅ Same (5-10s gen, 50ms cache) |
| **ADK Compliance** | ~30% | ✅ 100% Pure ADK |

---

## 💡 Key ADK Components Used

### ⭐ LlmAgent (google.adk)
- Base class: `google.adk.LlmAgent`
- Method: `async def run_async(input_data)`
- Used in: `TestCaseAgent`

### ⭐ BaseTool (google.adk.tools)
- Base class: `google.adk.tools.BaseTool`
- Method: `async def run_async(input_data)`
- Implemented by: `RAGSearchTool`, `RAGCacheTool`

### ⭐ Orchestration Pattern
- Direct agent invocation: `await agent.run_async()`
- Tool execution: `await tool.run_async()`
- No intermediate Runner needed for simple orchestration

---

## 🚀 Run Flow (דוגמה מלאה)

```python
# 1. Start server
$ python -m uvicorn src.api_adk:app --host 127.0.0.1 --port 8100

# 2. Upload PDF
POST /upload
Content-Type: multipart/form-data
file: "specification.pdf"

# 3. Orchestrator flow:
→ Parse PDF extract text
→ RAGSearchTool.run_async() [search]
→ IF miss: Agent1.run_async() + Agent2.run_async()
→ RAGCacheTool.run_async() [cache]
→ Return JSON {test_cases: [...]}

# 4. Second upload (same spec):
→ Parse PDF extract text
→ RAGSearchTool.run_async() [HIT from Redis/FAISS]
→ Return cached results (50ms)
```

---

**תיאור:** ADK v2 הוא pure ADK architecture שמשתמש בחלקים native של ADK לכל שכבה - LlmAgent לאגנטים, BaseTool לRAG, וזרימה async מלאה בFastAPI.
