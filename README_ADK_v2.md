# ADK Pure Orchestration Architecture (v2.0)

## Overview

This is a **pure Google ADK implementation** with:
- ✅ **ADK AsyncRunner** for agent orchestration
- ✅ **ADK Tools** for RAG (Redis caching + FAISS search)
- ✅ **Async FastAPI** endpoints
- ✅ **OpenAI gpt-4o-mini** via LiteLLM
- ✅ **Multi-agent coordination** via ADK

## Architecture

```
User Upload (PDF/JSON)
    ↓
FastAPI /upload (async)
    ↓
ADKTestCaseOrchestrator.run() 
    ├─ RAGSearchTool (ADK Tool)
    │  ├─ Redis check (exact hash match)
    │  ├─ FAISS search (semantic similarity > 0.7)
    │  └─ Return cached result OR "miss"
    │
    ├─ If MISS → ADK AsyncRunner.run_agent()
    │  ├─ Agent1 (LlmAgent subclass)
    │  │  └─ OpenAI gpt-4o-mini → 10 test cases
    │  └─ Agent2 (LlmAgent subclass)
    │     └─ OpenAI gpt-4o-mini → 10 test cases
    │
    └─ RAGCacheTool (ADK Tool)
       ├─ Store in Redis (24h TTL)
       └─ Index in FAISS
    ↓
Return to API
```

## Key Components

### 1. **ADK Orchestrator** (`src/agents/adk_orchestrator.py`)
```python
orchestrator = ADKTestCaseOrchestrator()  # Uses AsyncRunner internally
result = await orchestrator.run({"spec": "..."})
```

**What it does:**
- Manages agent lifecycle via ADK Runner
- Calls RAG tools before/after generation
- Handles async/await patterns

### 2. **ADK Tools** (`src/rag/adk_rag_tool.py`)
```python
class RAGSearchTool(Tool):
    async def execute(input_data) -> Dict
    
class RAGCacheTool(Tool):
    async def execute(input_data) -> Dict
```

**What they do:**
- `RAGSearchTool`: Check Redis + FAISS for cached specs
- `RAGCacheTool`: Store results and update indices

### 3. **ADK Agent** (`src/agents/google_adk_agent.py`)
```python
class TestCaseAgent(LlmAgent):
    async def run_async(self, input_data):
        # Called by ADK Runner
```

**What it does:**
- Subclasses ADK's LlmAgent
- Implements `run_async()` for orchestrator compatibility
- Generates test cases via OpenAI

### 4. **Async FastAPI** (`src/api_adk.py`)
```python
@app.post("/run")
async def run_agents(input_data: dict):
    results = await orchestrator.run(input_data)
```

## Flow Comparison

### Old (Custom Orchestrator)
```
POST /run
  → TestCaseOrchestrator.run() [sync]
    → RAGRetriever.lookup_or_generate()
      → Call agent sync wrapper
```

### New (ADK Pure)
```
POST /run [async]
  → ADKTestCaseOrchestrator.run() [async]
    → RAGSearchTool.execute() [async]
      → AsyncRunner.run_agent()
        → Agent1.run_async() [async]
        → Agent2.run_async() [async]
    → RAGCacheTool.execute() [async]
```

## Performance

| Scenario | Time | Source |
|----------|------|--------|
| First request (miss) | 5-10s | OpenAI generation |
| Cached (Redis hit) | 50ms | Redis |
| Similar (FAISS hit) | 100-200ms | FAISS + generation check |

## Testing

```bash
# Start server (async)
python -m uvicorn src.api_adk:app --host 127.0.0.1 --port 8100

# Upload PDF
curl -F "file=@spec.pdf" http://127.0.0.1:8100/upload

# Or POST JSON spec
curl -X POST http://127.0.0.1:8100/run \
  -H "Content-Type: application/json" \
  -d '{"spec": "User login..."}'
```

## Benefits of Pure ADK

✅ **No custom orchestration** — ADK Runner handles it  
✅ **Native async/await** — FastAPI + ADK aligned  
✅ **Tooling first** — RAG as ADK Tools  
✅ **Event-driven** — Async streams support  
✅ **Scalable** — ADK Runner can distribute agents  

## Dependencies Added

```
google-adk  (already had)
redis       (already had)
faiss-cpu   (already had)
openai      (already had)
fastapi     (updated for async)
```

## Files Changed

- `src/agents/adk_orchestrator.py` ← NEW (ADK Runner orchestrator)
- `src/rag/adk_rag_tool.py` ← NEW (ADK Tools)
- `src/agents/google_adk_agent.py` ← UPDATED (added `run_async()`)
- `src/api_adk.py` ← NEW (async FastAPI)

## What's Removed

❌ `TestCaseOrchestrator` (replaced by ADKTestCaseOrchestrator)  
❌ `RAGRetriever` (replaced by ADK Tools)  
❌ Custom sync wrapper (ADK Runner handles it)  
❌ Sync FastAPI (all async now)
