# Architecture Flow - Multi-Agent Test Case Generator

## System Overview
Multi-user test case generation system using **Google ADK (Agent Development Kit)** with intelligent routing.

---

## 🔄 Complete Flow Diagram

### Flow 1: File Upload → Auto Test Case Generation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. USER UPLOADS FILE                                                        │
│    POST /upload + PDF/TXT file + user-id header                            │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. API LAYER (FastAPI - NOT ADK)                                           │
│    - Receives file upload                                                   │
│    - Extracts user_id from header                                          │
│    - Routes to user's Orchestrator                                         │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. ORCHESTRATOR.handle_file_upload() (Custom - NOT ADK)                    │
│    - Gets/Creates orchestrator for user_id                                 │
│    - Parses file with FileParserTool                                       │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. SESSION STORAGE (Redis - NOT ADK)                                       │
│    Key: session:{user_id}                                                  │
│    Data: {files: [...], created_at, updated_at}                           │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. VECTOR SEARCH (FAISS - NOT ADK)                                         │
│    - Embeds file content using OpenAI text-embedding-ada-002              │
│    - Stores in per-user FAISS index                                        │
│    - Metadata: {file_name, type: "specification"}                         │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 6. AUTO-GENERATE REQUEST (Custom - NOT ADK)                                │
│    Creates message:                                                         │
│    "A specification file has been uploaded: 'filename.pdf'.                │
│     Please analyze and generate test cases.                                │
│     Specification content: [full text]"                                    │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 7. ORCHESTRATOR.handle_chat() (Custom - NOT ADK)                           │
│    - Receives auto-generated message                                       │
│    - Calls Router Agent to decide which agent to use                       │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 8. ROUTER AGENT - _route_to_agent() (✅ GOOGLE ADK)                        │
│    ┌─────────────────────────────────────────────────────┐                │
│    │ LlmAgent (ADK)                                      │                │
│    │  - model: LiteLlm(model="openai/gpt-4o-mini") (ADK)│                │
│    │  - name: "router_agent_{user_id}"                  │                │
│    │  - instruction: "You are an intelligent router..." │                │
│    └─────────────────────────────────────────────────────┘                │
│                                                                             │
│    ┌─────────────────────────────────────────────────────┐                │
│    │ InMemorySessionService (✅ ADK)                     │                │
│    │  - Manages ADK session per router                  │                │
│    │  - session_id: stored in self.router_session_id   │                │
│    └─────────────────────────────────────────────────────┘                │
│                                                                             │
│    ┌─────────────────────────────────────────────────────┐                │
│    │ Runner (✅ ADK)                                      │                │
│    │  - runner.run_async(user_id, session_id, message) │                │
│    │  - Returns async stream of events                  │                │
│    └─────────────────────────────────────────────────────┘                │
│                                                                             │
│    Output: "test_case_agent"                                               │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 9. ORCHESTRATOR - Route to Selected Agent (Custom Logic)                   │
│    - Checks: if agent_name == "test_case_agent"                           │
│    - Prepares input: {"spec": message} ← FIX: was {"message": ...}        │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 10. TEST CASE AGENT - process() (Custom + ✅ ADK)                          │
│     ┌──────────────────────────────────────────────────┐                  │
│     │ A. Check Redis Cache (NOT ADK)                   │                  │
│     │    Key: test_cases:{hash(spec)}                  │                  │
│     │    If found → return cached result               │                  │
│     └──────────────────┬───────────────────────────────┘                  │
│                        │ Cache miss                                        │
│                        ▼                                                   │
│     ┌──────────────────────────────────────────────────┐                  │
│     │ B. Check FAISS Similarity (NOT ADK)              │                  │
│     │    Search for similar specs (threshold: 0.85)    │                  │
│     │    If found + valid → return cached result       │                  │
│     └──────────────────┬───────────────────────────────┘                  │
│                        │ No similar spec                                   │
│                        ▼                                                   │
│     ┌──────────────────────────────────────────────────┐                  │
│     │ C. Generate with ADK (✅ GOOGLE ADK)             │                  │
│     │                                                   │                  │
│     │    LlmAgent (ADK)                                │                  │
│     │     - model: LiteLlm(model="openai/gpt-4o-mini")│                  │
│     │     - name: "test_case_agent_{user_id}"         │                  │
│     │     - instruction: "You are a senior QA..."     │                  │
│     │                                                   │                  │
│     │    InMemorySessionService (✅ ADK)               │                  │
│     │     - session_id: gen_{user_id}_{hash(spec)}    │                  │
│     │                                                   │                  │
│     │    Runner (✅ ADK)                                │                  │
│     │     - Executes LlmAgent                          │                  │
│     │     - Streams events with AI responses           │                  │
│     │                                                   │                  │
│     │    Response Format (JSON):                       │                  │
│     │     {                                             │                  │
│     │       "test_cases": [{                           │                  │
│     │         "id": "TC001",                           │                  │
│     │         "title": "...",                          │                  │
│     │         "priority": "high",                      │                  │
│     │         "steps": [...],                          │                  │
│     │         "expected_result": "...",                │                  │
│     │         "tags": [...]                            │                  │
│     │       }],                                        │                  │
│     │       "total_count": 10,                         │                  │
│     │       "coverage_areas": [...]                    │                  │
│     │     }                                             │                  │
│     └──────────────────┬───────────────────────────────┘                  │
│                        │                                                   │
│                        ▼                                                   │
│     ┌──────────────────────────────────────────────────┐                  │
│     │ D. Cache Result (NOT ADK)                        │                  │
│     │    - Redis: test_cases:{hash(spec)}             │                  │
│     │    - FAISS: Store with metadata                  │                  │
│     └──────────────────────────────────────────────────┘                  │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 11. RETURN TO USER                                                          │
│     {                                                                       │
│       "response": "File uploaded successfully. Generated 10 test cases",   │
│       "file_name": "spec.pdf",                                             │
│       "test_cases": [...],                                                 │
│       "total_count": 10,                                                   │
│       "coverage_areas": [...],                                             │
│       "agent_used": "test_case_agent"                                      │
│     }                                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Flow 2: Direct Chat Message

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. USER SENDS CHAT MESSAGE                                                 │
│    POST /chat + {"message": "Generate login test cases"} + user-id        │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. ORCHESTRATOR.handle_chat()                                              │
│    - Routes to Router Agent (✅ ADK LlmAgent)                              │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. ROUTER AGENT (✅ ADK) → Returns "test_case_agent"                       │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. TEST CASE AGENT (✅ ADK) → Generates test cases                         │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. RETURN RESULTS TO USER                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Technology Stack

### ✅ Google ADK Components Used:

| Component | Usage | Location |
|-----------|-------|----------|
| **LlmAgent** | Router agent + TestCaseAgent | `orchestrator.py`, `test_case_agent.py` |
| **LiteLlm** | Model wrapper for OpenAI | Both agents use `LiteLlm(model="openai/gpt-4o-mini")` |
| **Runner** | Execute agents and stream events | `runner.run_async()` in both router and test agent |
| **InMemorySessionService** | ADK session management | Per-agent session handling |
| **InMemoryArtifactService** | Artifact storage | Test case agent |

### 🔧 Non-ADK Components:

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Redis** | Global session + cache | `redis-py` (asyncio) |
| **FAISS** | Vector similarity search | `faiss-cpu` + OpenAI embeddings |
| **FastAPI** | API endpoints | `fastapi` + `uvicorn` |
| **FileParserTool** | Parse PDF/TXT files | `PyPDF2` |
| **Orchestrator** | Multi-user coordination | Custom Python class |

---

## 🔑 Key Fixes in This Commit

### 1. **Router Session Management** (Fixed)
**Problem**: Tried to access `sessions[0]` but `list_sessions()` returns `ListSessionsResponse` object

**Solution**: Store `router_session_id` during initialization and use it directly
```python
# Before (BROKEN):
sessions = await self.adk_session_service.list_sessions(...)
session_id = sessions[0].id  # ❌ TypeError

# After (FIXED):
self.router_session_id = adk_session.id  # ✅ Store during init
# Use self.router_session_id directly
```

### 2. **Agent Input Format** (Fixed)
**Problem**: TestCaseAgent expected `{"spec": "..."}` but received `{"message": "..."}`

**Solution**: Route-specific input formatting in `handle_chat()`
```python
# Before (BROKEN):
result = await agent.process({
    "action": "chat",
    "message": message  # ❌ TestCaseAgent expects "spec"
})

# After (FIXED):
if agent_name == "test_case_agent":
    result = await agent.process({
        "spec": message  # ✅ Correct format
    })
else:
    result = await agent.process({
        "action": "chat",
        "message": message
    })
```

---

## 📊 Current Status

✅ **Working Features:**
- Multi-user orchestration (one Orchestrator per user)
- File upload with auto test case generation
- Intelligent routing with Router Agent (ADK LlmAgent)
- Test case generation with TestCaseAgent (ADK LlmAgent)
- Redis caching (global)
- FAISS semantic search (per-user)
- FastAPI async endpoints

✅ **ADK Integration:**
- Pure Google ADK agents (LlmAgent + LiteLlm)
- ADK Runner with event streaming
- ADK session management (InMemorySessionService)
- No direct OpenAI client usage

---

## 🚀 Next Steps

- Add more specialized agents (e.g., SummaryAgent, AnalysisAgent)
- Router will automatically route to correct agent
- Each agent can have its own input/output format
- Orchestrator handles the routing logic

---

**Generated**: 2025-11-25  
**Version**: 2.0  
**Branch**: new_version_adk
