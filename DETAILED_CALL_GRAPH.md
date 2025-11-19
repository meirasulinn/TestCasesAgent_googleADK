# 📊 גרף ויזואלי של "מי קורא למי"

## 🔴 DEPRECATED FILES (v1.0 - לא בשימוש):

```
┌──────────────────────────────────┐
│ ❌ api.py (OLD - NOT RUNNING)    │
│                                  │
│  Endpoint: POST /upload          │
│  ↓                               │
│  uploads → orchestrator.run()    │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│ ❌ test_case_orchestrator.py (OLD)          │
│  class TestCaseOrchestrator:                 │
│                                              │
│  def run(input_spec):                        │
│  ├─ RAGRetriever.lookup_or_generate()       │
│  │  ├─ Check Redis                          │
│  │  └─ Check FAISS                          │
│  │                                          │
│  └─ _generate_test_cases(spec)              │
│     ├─ FOR agent in agents:                 │
│     │  └─ generate_test_cases_sync(spec)    │
│     └─ RETURN results                       │
└──────────────┬───────────────────────────────┘
               │
        ┌──────┴──────┐
        │             │
        ▼             ▼
   ❌ RAGRetriever  ❌ generate_test_cases_sync()
      (retrieval.py)   (from google_adk_agent.py)
```

---

## 🟢 ACTIVE FILES (v2.0 - בשימוש כרגע):

```
┌────────────────────────────────────┐
│ ✅ api_adk.py (NEW - RUNNING)      │
│                                    │
│ Endpoint: POST /upload             │
│ async def upload_endpoint()        │
│  ↓                                 │
│  uploads → await orchestrator.run()
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────┐
│ ✅ adk_orchestrator.py (NEW)                        │
│  class ADKTestCaseOrchestrator:                      │
│                                                      │
│  async def run(input_spec):                          │
│  ├─ await RAGSearchTool.run_async()                 │
│  │  ├─ Check Redis                                 │
│  │  └─ Check FAISS                                 │
│  │                                                  │
│  ├─ (if miss) await agent.run_async()              │
│  │  FOR agent IN [Agent1, Agent2]                 │
│  │  └─ Call OpenAI                                │
│  │                                                  │
│  └─ await RAGCacheTool.run_async()                 │
│     ├─ Store in Redis                             │
│     └─ Index in FAISS                             │
└────────┬───────────┬────────────┬─────────────┘
         │           │            │
         ▼           ▼            ▼
    [RAGSearchTool] [Agents]  [RAGCacheTool]
     (BaseTool)   (LlmAgent)    (BaseTool)
```

---

## 🎯 Agents - עדיף לקחת בחשבון:

```
┌────────────────────────────────────────────┐
│ ✅ google_adk_agent.py (NEW - IN USE)      │
│                                            │
│ class TestCaseAgent(LlmAgent):             │
│   ├─ async def run_async(input_data)      │
│   │  └─ Calls: generate_test_cases_sync() │
│   │     └─ OpenAI API (gpt-4o-mini)       │
│   │                                        │
│   └─ RETURNS: {test_cases: [...]}         │
│                                            │
│  Instances created in api_adk.py:         │
│  agent1 = TestCaseAgent("Agent1")         │
│  agent2 = TestCaseAgent("Agent2")         │
│                                            │
│  Status: ✅ WORKING (tested)              │
└────────────────────────────────────────────┘


❌ test_case_agent.py (OLD - NOT USED)
   ├─ class TestCaseAgent(Agent)       [זקן]
   │  └─ def execute()
   │     └─ Returns mock data
   │
   └─ class TestCaseRunner(Runner)     [זקן]
      └─ def run()
         └─ For each agent: execute()

   Status: ❌ NOT IMPORTED ANYWHERE
   Problem: שם זהה ל- google_adk_agent.py!
```

---

## 📁 Full File Map:

```
adk_TestCaseAgent_poc/
│
├── ✅ src/api_adk.py                    [v2.0 - IN USE]
│   └─ IMPORTS: ADKTestCaseOrchestrator
│                TestCaseAgent (from google_adk_agent.py)
│
├── ❌ src/api.py                        [v1.0 - NOT USED]
│   └─ IMPORTS: TestCaseOrchestrator
│                TestCaseAgent (from google_adk_agent.py)
│
├── src/agents/
│   │
│   ├── ✅ google_adk_agent.py           [v2.0 - IN USE]
│   │   └─ TestCaseAgent(LlmAgent)
│   │    └─ USED BY: api_adk.py
│   │
│   ├── ❌ test_case_agent.py            [v1.0 - OLD]
│   │   ├─ TestCaseAgent(Agent)         [זקן - שם זהה!]
│   │   └─ TestCaseRunner(Runner)
│   │    └─ NOT IMPORTED BY ANYONE
│   │
│   ├── ✅ adk_orchestrator.py           [v2.0 - IN USE]
│   │   └─ ADKTestCaseOrchestrator
│   │    └─ USED BY: api_adk.py
│   │
│   └── ❌ test_case_orchestrator.py     [v1.0 - OLD]
│       └─ TestCaseOrchestrator
│        └─ USED BY: api.py (שלא בשימוש)
│
├── src/rag/
│   │
│   ├── ✅ adk_rag_tool.py               [v2.0 - IN USE]
│   │   ├─ RAGSearchTool(BaseTool)
│   │   └─ RAGCacheTool(BaseTool)
│   │    └─ USED BY: adk_orchestrator.py
│   │
│   └── ❌ retrieval.py                  [v1.0 - OLD]
│       └─ RAGRetriever
│        └─ USED BY: test_case_orchestrator.py
│
└── ❌ main.py                            [מצביע על api.py - צריך לתקן]
    └─ Runs: src.api:app                 [v1.0]
       Should be: src.api_adk:app        [v2.0]
```

---

## ⚠️ הבעיות בדיוק:

### **בעיה #1: TestCaseAgent מופיע פעמיים**
```
FILE 1: google_adk_agent.py
class TestCaseAgent(LlmAgent):          ✅ IN USE, WORKING
    def run_async():  
        ↓
        OpenAI API call
        ↓
        Returns test cases

FILE 2: test_case_agent.py
class TestCaseAgent(Agent):             ❌ NOT USED, MOCK
    def execute():
        ↓
        Returns ["TestCase1", "TestCase2"]

CONFLICT: Same name, different implementations!
```

### **בעיה #2: api.py vs api_adk.py**
```
FILE 1: api.py                          ❌ v1.0 - NOT RUNNING
FILE 2: api_adk.py                      ✅ v2.0 - RUNNING (בידנית)

main.py still points to api.py!
```

### **בעיה #3: TestCaseOrchestrator vs ADKTestCaseOrchestrator**
```
FILE 1: test_case_orchestrator.py       ❌ v1.0 - NOT USED
FILE 2: adk_orchestrator.py             ✅ v2.0 - IN USE
```

### **בעיה #4: retrieval.py vs adk_rag_tool.py**
```
FILE 1: retrieval.py                    ❌ v1.0 - NOT USED
FILE 2: adk_rag_tool.py                 ✅ v2.0 - IN USE
```

---

## 🎯 הערות סיום:

### ✅ מה עובד:
- v2.0 architecture בפועל עובדת מצוין
- Agents עובדים (Agent1 + Agent2)
- RAG caching עובד (Redis + FAISS)
- OpenAI integration עובד

### ❌ מה מיותר:
- `api.py` - old version
- `test_case_orchestrator.py` - old version
- `test_case_agent.py` - old version (duplicate name!)
- `retrieval.py` - old version
- `main.py` - מצביע על הישן

### 🔧 מה צריך לתקן:
1. מחק את הקבצים הישנים (v1.0)
2. עדכן `main.py` ל-`api_adk:app`
3. Rename או מחק את `test_case_agent.py` כי אין מה שיחוצה אותו

---

## 📝 סיכום העצות:

**אם אתה רוצה להשאיר v1.0 לעזיבה וللוודות ויקום גם v2.0:**
- Move `api.py`, `test_case_orchestrator.py`, `retrieval.py` into `src/old_v1/`
- Rename `test_case_agent.py` to `test_case_agent_deprecated.py` כדי להימנע מ-name collision

**אם אתה רוצה להישאר only עם v2.0 (recommended):**
- Delete: `api.py`, `test_case_orchestrator.py`, `retrieval.py`, `test_case_agent.py`
- Update: `main.py` to point to `api_adk:app`
- Keep: `api_adk.py`, `adk_orchestrator.py`, `google_adk_agent.py`, `adk_rag_tool.py`
