# 🔍 ניתוח "מי קורא למי" - גרף Dependency

## 📊 גרף הקריאות המלא

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENT (Postman)                            │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                    POST /upload (PDF)
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
        ┌─────────────────────┐   ┌─────────────────────┐
        │   api_adk.py        │   │   api.py [OLD]      │
        │   (v2.0 - IN USE)   │   │   (v1.0 - NOT USED) │
        │                     │   │                     │
        │ upload_endpoint()   │   │ upload_file()       │
        └──────────┬──────────┘   └──────────┬──────────┘
                   │                         │
                   │ קורא ל-                 │ קורא ל-
                   ▼                         ▼
        ┌──────────────────────────┐    ┌────────────────────────┐
        │ ADKTestCaseOrchestrator  │    │ TestCaseOrchestrator   │
        │ (adk_orchestrator.py)    │    │ (test_case_orchestr..) │
        │ ⭐ [ADK v2 - IN USE]    │    │ [v1.0 - NOT USED]      │
        │                          │    │                        │
        │ async def run()           │    │ def run()              │
        └──────────┬───────────────┘    └──────────┬─────────────┘
                   │                              │
        ┌──────────┴───────────────────────┐     │
        │                                  │     │ קורא ל-
        │ צריך (NEEDS):                   │     │
        │ - RAGSearchTool()                │     ▼
        │ - Agent1.run_async()             │ (קורא ל-RAGRetriever.lookup)
        │ - Agent2.run_async()             │
        │ - RAGCacheTool()                 │
        │                                  │
        ▼                                  ▼
    ┌─────────────────────┐         ┌──────────────────────┐
    │ RAGSearchTool       │         │ RAGRetriever         │
    │ (adk_rag_tool.py)   │         │ (retrieval.py)       │
    │ ⭐ [ADK BaseTool]   │         │ [v1.0 - OLD]         │
    │                     │         │                      │
    │ run_async()         │         │ lookup_or_generate() │
    └──────────┬──────────┘         └─────────┬────────────┘
               │                             │
               ▼                             ▼
        Redis + FAISS               Redis + FAISS
        (Cache Search)              (Cache Search)
               │
               │ HIT or MISS
               │
               ▼
        ┌─────────────────────────────────────────┐
        │ IF MISS → Agents are called             │
        │                                         │
        │    Agent1 (v2.0)    Agent2 (v2.0)      │
        │  ⭐[ADK LlmAgent]  ⭐[ADK LlmAgent]    │
        │  google_adk_agent  google_adk_agent     │
        │                                         │
        │    async def run_async()                │
        │    ├─ OpenAI Call (gpt-4o-mini)        │
        │    └─ Parse 10 test cases              │
        │                                         │
        └──────────────┬─────────────────────────┘
                       │
                       ▼
        ┌─────────────────────────────────────────┐
        │ Results combined: 19-22 test cases      │
        │                                         │
        │ [NOT CALLED]: TestCaseAgent (old)       │
        │ [NOT CALLED]: test_case_agent.py        │
        │ [NOT CALLED]: TestCaseRunner (old)      │
        └──────────────┬─────────────────────────┘
                       │
                       ▼
        ┌─────────────────────────────────────────┐
        │ RAGCacheTool                            │
        │ (adk_rag_tool.py)                       │
        │ ⭐ [ADK BaseTool]                       │
        │                                         │
        │ run_async()                             │
        │ ├─ Store in Redis (TTL: 24h)           │
        │ └─ Index in FAISS                       │
        └──────────────┬─────────────────────────┘
                       │
                       ▼
                  Return to Client
```

---

## 🎯 סיכום מי קורא למי:

### **בשימוש כרגע (v2.0):**
```
api_adk.py
    ↓ קורא ל-
ADKTestCaseOrchestrator (adk_orchestrator.py)
    ↓ קורא ל-
├─ RAGSearchTool (adk_rag_tool.py)
├─ Agent1.run_async() [google_adk_agent.py]
├─ Agent2.run_async() [google_adk_agent.py]
└─ RAGCacheTool (adk_rag_tool.py)
```

### **לא בשימוש כרגע (v1.0 - מיותר):**
```
❌ api.py (OLD)
    ↓ קורא ל-
❌ TestCaseOrchestrator (test_case_orchestrator.py)
    ↓ קורא ל-
❌ RAGRetriever (retrieval.py)

❌ test_case_agent.py (זה agent זקן שלא בשימוש)

❌ main.py מצביע על api.py (v1.0)
```

---

## 🚨 בעיות שזיהיתי:

### **1️⃣ TestCaseAgent - מופיע פעמיים בשם זהה!**

```
📍 FILE 1: src/agents/google_adk_agent.py
   class TestCaseAgent(LlmAgent):  ✅ IN USE (v2.0)
   - Inherits from google.adk.LlmAgent
   - Has run_async() method
   - Calls OpenAI API

📍 FILE 2: src/agents/test_case_agent.py
   class TestCaseAgent(Agent):     ❌ NOT USED (v1.0 - OLD)
   - Inherits from google.adk.Agent
   - Has execute() method
   - Just returns mock data

⚠️ PROBLEM: זה יוצר confusion! יש שני קבצים עם class בעל שם זהה!
```

---

### **2️⃣ API Files - מופיעים פעמיים!**

```
📍 FILE 1: src/api_adk.py
   ✅ IN USE (v2.0)
   - async def upload_endpoint()
   - Creates: Agent1, Agent2 (from google_adk_agent.py)
   - Uses: ADKTestCaseOrchestrator (adk_orchestrator.py)
   - Status: RUNNING NOW on port 8100

📍 FILE 2: src/api.py
   ❌ NOT USED (v1.0 - OLD)
   - def upload_file()
   - Creates: Agent1, Agent2 (from google_adk_agent.py)
   - Uses: TestCaseOrchestrator (test_case_orchestrator.py)
   - Status: NOT IN USE

⚠️ PROBLEM: יש שתי API endpoints עם אותה שם! אם מישהו קורא ל-api.py הוא יקבל את v1.0
```

---

### **3️⃣ Orchestrator Files - מופיעים פעמיים!**

```
📍 FILE 1: src/agents/adk_orchestrator.py
   class ADKTestCaseOrchestrator  ✅ IN USE (v2.0)
   - Uses: RAGSearchTool(BaseTool) [ADK]
   - Uses: RAGCacheTool(BaseTool) [ADK]
   - Calls: agent.run_async() directly
   - async def run()

📍 FILE 2: src/agents/test_case_orchestrator.py
   class TestCaseOrchestrator     ❌ NOT USED (v1.0 - OLD)
   - Uses: RAGRetriever (custom class)
   - Calls: generate_test_cases_sync()
   - def run()

⚠️ PROBLEM: יש שתי orchestrators! אחד מיותר
```

---

### **4️⃣ RAG Files - מופיעים פעמיים!**

```
📍 FILE 1: src/rag/adk_rag_tool.py
   class RAGSearchTool(BaseTool)  ✅ IN USE (v2.0)
   class RAGCacheTool(BaseTool)   ✅ IN USE (v2.0)
   - Inherits from google.adk.tools.BaseTool [ADK]
   - async def run_async()

📍 FILE 2: src/rag/retrieval.py
   class RAGRetriever             ❌ NOT USED (v1.0 - OLD)
   - Custom class (not ADK)
   - def lookup_or_generate()
   - def _search_cache()

⚠️ PROBLEM: יש שתי implementations של RAG! אחד מיותר
```

---

### **5️⃣ main.py מצביע על api.py (v1.0 ישנה!)**

```python
# main.py
subprocess.run([
    sys.executable, "-m", "uvicorn",
    "src.api:app",           # ❌ זה מפעיל את v1.0!
    "--host", "127.0.0.1",
    "--port", "8100"
])
```

עכשיו אתה מפעיל ידנית את `api_adk.py` כי `main.py` עדיין מצביע על הישן.

---

## 📈 סיכום - מה מיותר:

| קובץ | סטטוס | הערה |
|------|--------|------|
| `src/api_adk.py` | ✅ KEEP | זה הAPI הנכון (v2.0) |
| `src/api.py` | ❌ DELETE | v1.0 - מיותר |
| `src/agents/adk_orchestrator.py` | ✅ KEEP | זה ה-orchestrator הנכון (v2.0) |
| `src/agents/test_case_orchestrator.py` | ❌ DELETE | v1.0 - מיותר |
| `src/agents/google_adk_agent.py` | ✅ KEEP | זה ה-agent הנכון (v2.0) |
| `src/agents/test_case_agent.py` | ❌ DELETE | v1.0 - מיותר (TestCaseAgent וגם TestCaseRunner) |
| `src/rag/adk_rag_tool.py` | ✅ KEEP | זה ה-RAG הנכון (v2.0) |
| `src/rag/retrieval.py` | ❌ DELETE | v1.0 - מיותר |
| `main.py` | 🔧 UPDATE | צריך לשנות ל-`api_adk:app` |

---

## 🎯 גרף שלCalling Path (מה שקורה כרגע):

```
✅ CURRENT (v2.0):

Client POST /upload
    ↓
api_adk.py::upload_endpoint() [async]
    ↓
ADKTestCaseOrchestrator.run() [async]
    ├─ RAGSearchTool.run_async() [ADK BaseTool]
    │  ├─ Redis lookup
    │  └─ FAISS search
    │
    ├─ (if miss) Agent1.run_async() [ADK LlmAgent] 
    │  └─ OpenAI API call
    │
    ├─ (if miss) Agent2.run_async() [ADK LlmAgent]
    │  └─ OpenAI API call
    │
    └─ RAGCacheTool.run_async() [ADK BaseTool]
       ├─ Redis store
       └─ FAISS index

✅ Return JSON with 19-22 test cases
```

---

## 💡 המלצות:

### **דברים שטעוני שינוי:**

1. **מחק את הקבצים הישנים (v1.0):**
   - `src/api.py` - לא בשימוש, רק מבלבל
   - `src/agents/test_case_orchestrator.py` - לא בשימוש
   - `src/agents/test_case_agent.py` - לא בשימוש ויש TestCaseAgent זהה ב-google_adk_agent.py
   - `src/rag/retrieval.py` - לא בשימוש

2. **עדכן את main.py:**
   ```python
   "src.api_adk:app",  # תחליף את "src.api:app"
   ```

3. **מתן שמות ברור:**
   - כל v1.0 files צריך להיות ב-folder נפרד או לומחוק

---

## 🔴 Agents זקנים שצריך להוריד:

```
❌ src/agents/test_case_agent.py
   - class TestCaseAgent(Agent) - זקן, לא בשימוש
   - class TestCaseRunner(Runner) - זקן, לא בשימוש
   - לא עובד עם v2.0

✅ תחליף אם יש agents אחרים?
   - Google_adk_agent.py כבר מכיל Agent1 ו-Agent2
   - No need for old test_case_agent.py
```

---

## 🎬 סיכום סופי:

**הבעיה:** יש שני מערכות בעמודה זה:
- **v1.0** (old) - api.py → test_case_orchestrator.py → retrieval.py
- **v2.0** (new) - api_adk.py → adk_orchestrator.py → adk_rag_tool.py

**מה קורה כרגע:**
- ✅ הגרסה v2.0 עובדת והיא בשימוש
- ❌ אבל הגרסה v1.0 עדיין בקוד, רק לא בשימוש

**ההמלצה:**
- 🗑️ מחק את כל v1.0 files (אם לא צריך אותם יותר)
- ✅ תשמר על v2.0 files (עובדים)
- 🔧 עדכן main.py ל-api_adk.py
