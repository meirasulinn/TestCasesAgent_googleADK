# 🔍 FAISS + Redis - Complete Flow Analysis

## מי מנהל מה? סקירה כללית

```
┌─────────────────────────────────────────────────────────────────┐
│                    REDIS (SessionManager)                        │
│           Global, Persistent, Shared (by key)                    │
│                                                                  │
│  מנוהל על ידי: SessionManager (singleton)                       │
│  נוצר: בהתקנה הראשונה של המערכת                                │
│  חיים: Persistent (שורד restart)                                │
│  שיתוף: משותף בין users (מבודד לפי keys)                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    FAISS (FAISSService)                          │
│          Per-User, In-Memory, Isolated                           │
│                                                                  │
│  מנוהל על ידי: Orchestrator (instance per user)                │
│  נוצר: כשנוצר Orchestrator חדש ליוזר                           │
│  חיים: In-memory (נמחק ב-restart)                               │
│  שיתוף: אין! כל user מקבל instance משלו                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📍 היכן FAISS נוצר ונמצא?

### מיקום 1: Orchestrator (תמיד!)

**קובץ:** `src/orchestrator/orchestrator.py`

```python
class Orchestrator:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.session_manager = session_manager  # ← Redis (singleton shared)
        self.faiss_service = FAISSService(user_id)  # ← FAISS (NEW per user!)
        # ...
```

**מתי נוצר:**
- כש-`get_orchestrator(user_id)` נקרא בפעם הראשונה ליוזר
- קורה ב-`src/api/api.py` בכל endpoint שמקבל `user-id` header

**כמה instances:**
- 1 FAISS לכל user
- אליס → FAISSService("alice")
- בוב → FAISSService("bob")
- **מבודדים לחלוטין!**

---

### מיקום 2: TestCaseAgent (מקבל reference מ-Orchestrator)

**קובץ:** `src/agents/test_case_agent.py`

```python
class TestCaseAgent(BaseAgent):
    def __init__(self, user_id: str, session_manager, faiss_service):
        super().__init__(...)
        self.faiss_service = faiss_service  # ← מקבל מה-Orchestrator!
        # ...
```

**חשוב:** TestCaseAgent **לא יוצר** FAISS חדש - הוא מקבל reference לאותו instance שנוצר ב-Orchestrator!

---

### מיקום 3: WeatherAgent & TimeAgent (לא משתמשים ב-FAISS!)

```python
class WeatherAgent(BaseAgent):
    def __init__(self, user_id: str, session_manager):
        # אין faiss_service! רק session_manager
        # ...
```

**למה?** כי Weather ו-Time לא צריכים חיפוש סמנטי - הם עושים פעולות פשוטות!

---

## 🔄 פלואו מלא: מתי FAISS משמש?

### תרחיש 1: העלאת קובץ (File Upload)

```
┌─────────────────────────────────────────────────────────────────┐
│ USER: POST /upload                                               │
│ Headers: user-id: alice                                          │
│ Body: {file: "login_spec.pdf"}                                  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ API Handler (src/api/api.py)                                    │
│   orchestrator = await get_orchestrator("alice")                │
│   result = await orchestrator.handle_file_upload(...)           │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ Orchestrator.handle_file_upload()                               │
│ (src/orchestrator/orchestrator.py - line ~252)                  │
│                                                                  │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ STEP 1: Parse File                                        │  │
│ │   parse_result = file_parser.run_async(...)              │  │
│ │   text_content = "Login specification: ..."              │  │
│ └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ STEP 2: Save to Redis (SessionManager)                   │  │
│ │   await session_manager.add_file_to_session(             │  │
│ │       user_id="alice",                                    │  │
│ │       file_info={                                         │  │
│ │           "name": "login_spec.pdf",                       │  │
│ │           "type": "pdf",                                  │  │
│ │           "content": text_content,                        │  │
│ │           "size": 12345                                   │  │
│ │       }                                                    │  │
│ │   )                                                        │  │
│ │                                                            │  │
│ │   Redis State:                                            │  │
│ │   session:alice → {                                       │  │
│ │       files: [                                            │  │
│ │           {name: "login_spec.pdf", content: "...", ...}  │  │
│ │       ]                                                    │  │
│ │   }                                                        │  │
│ └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ STEP 3: Add to FAISS  ← כאן FAISS נכנס לתמונה!          │  │
│ │   self.faiss_service.add_document(                        │  │
│ │       text=text_content,                                  │  │
│ │       metadata={"file_name": file_name, "type": "spec"}  │  │
│ │   )                                                        │  │
│ │                                                            │  │
│ │   מה קורה בפנים? (src/services/faiss_service.py)        │  │
│ │   ↓                                                        │  │
│ │   1. OpenAI Embedding API                                 │  │
│ │      text → embedding vector [1536 dims]                  │  │
│ │                                                            │  │
│ │   2. FAISS Index Add                                      │  │
│ │      self.index.add(vector)                               │  │
│ │                                                            │  │
│ │   3. Store Original Text                                  │  │
│ │      self.documents.append(text_content)                  │  │
│ │                                                            │  │
│ │   4. Store Metadata                                       │  │
│ │      self.metadata.append({"file_name": ..., ...})       │  │
│ │                                                            │  │
│ │   FAISS State (in memory):                                │  │
│ │   alice's FAISS → {                                       │  │
│ │       index: [vector0],                                   │  │
│ │       documents: ["Login specification..."],              │  │
│ │       metadata: [{"file_name": "login_spec.pdf"}]        │  │
│ │   }                                                        │  │
│ └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ STEP 4: Auto-generate test cases                          │  │
│ │   result = await handle_chat(                             │  │
│ │       "Generate test cases for login_spec.pdf..."         │  │
│ │   )                                                        │  │
│ │   ↓                                                        │  │
│ │   (ראה תרחיש 2 למטה)                                      │  │
│ └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

📊 סיכום STEP 3:
✅ FAISS נשמר רק ב-memory (in Orchestrator instance)
✅ Redis נשמר ב-disk (persistent)
✅ FAISS משמש לחיפוש סמנטי מהיר
✅ Redis משמש לשמירת קבצים והיסטוריה
```

---

### תרחיש 2: צ'אט עם בקשה ל-test cases

```
┌─────────────────────────────────────────────────────────────────┐
│ USER: POST /chat                                                 │
│ Headers: user-id: alice                                          │
│ Body: {message: "Generate test cases for login feature"}        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ Orchestrator.handle_chat()                                       │
│                                                                  │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ STEP 1: Router Agent decides                              │  │
│ │   agent_name = await _route_to_agent(message)             │  │
│ │   → Returns: "test_case_agent"                            │  │
│ └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ STEP 2: Get agent                                         │  │
│ │   agent = self.agents["test_case_agent"]                  │  │
│ └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ STEP 3: Execute agent                                     │  │
│ │   result = await agent.process({"spec": message})         │  │
│ └───────────────────────┬─────────────────────────────────────┘│
└────────────────────────┼──────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ TestCaseAgent.process()                                          │
│ (src/agents/test_case_agent.py - line ~130)                     │
│                                                                  │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ CACHE CHECK 1: Redis Cache                                │  │
│ │   cache_key = f"test_cases:{hash(spec_text)}"             │  │
│ │   cached = await session_manager.get_cache(cache_key)     │  │
│ │   ↓                                                        │  │
│ │   Redis.get("cache:test_cases:a1b2c3d4e5f6")             │  │
│ │   → None (first time)                                      │  │
│ └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ CACHE CHECK 2: FAISS Similarity Search  ← כאן FAISS!      │  │
│ │   similar = self.faiss_service.search(spec_text, top_k=1) │  │
│ │                                                            │  │
│ │   מה קורה בפנים? (src/services/faiss_service.py)        │  │
│ │   ↓                                                        │  │
│ │   1. Create Query Embedding                               │  │
│ │      query_text → OpenAI API → query_vector [1536]       │  │
│ │                                                            │  │
│ │   2. FAISS Search                                         │  │
│ │      distances, indices = self.index.search(              │  │
│ │          query_vector,                                     │  │
│ │          k=1                                               │  │
│ │      )                                                     │  │
│ │                                                            │  │
│ │   3. Calculate Similarity                                 │  │
│ │      similarity = 1 / (1 + distance)                      │  │
│ │                                                            │  │
│ │   4. Check Threshold                                      │  │
│ │      if similarity >= 0.85:  # FAISS_SIMILARITY_THRESHOLD│  │
│ │          return results with metadata                     │  │
│ │                                                            │  │
│ │   תוצאה:                                                  │  │
│ │   [                                                        │  │
│ │       {                                                    │  │
│ │           "text": "Login specification...",               │  │
│ │           "metadata": {                                   │  │
│ │               "file_name": "login_spec.pdf",              │  │
│ │               "test_cases": {  ← יש cache!               │  │
│ │                   test_cases: [...],                      │  │
│ │                   total_count: 10                         │  │
│ │               }                                            │  │
│ │           },                                               │  │
│ │           "similarity": 0.96  ← גבוה מאוד!               │  │
│ │       }                                                    │  │
│ │   ]                                                        │  │
│ └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ DECISION: FAISS Cache Hit! (similarity > 0.95)            │  │
│ │   if similar[0]['similarity'] > 0.95:                     │  │
│ │       cached_result = similar[0]['metadata']['test_cases']│  │
│ │       return cached_result  ← ממטמון FAISS!              │  │
│ │                                                            │  │
│ │   ⚡ חוסך קריאה ל-OpenAI API!                             │  │
│ │   ⚡ תגובה מהירה (milliseconds במקום seconds)             │  │
│ └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│ ┌───────────────────────────────────────────────────────────┐  │
│ │ אם אין cache ב-FAISS → GENERATE NEW                       │  │
│ │   result = await _generate_with_adk(spec_text)            │  │
│ │   ↓                                                        │  │
│ │   1. קריאה ל-OpenAI API (gpt-4o-mini)                     │  │
│ │   2. ייצור test cases                                     │  │
│ │   3. שמירה ב-Redis cache                                  │  │
│ │      await session_manager.set_cache(cache_key, result)   │  │
│ │      Redis: cache:test_cases:xxx → {...}                  │  │
│ │   4. שמירה ב-FAISS metadata  ← כאן FAISS שוב!           │  │
│ │      self.faiss_service.add_document(                     │  │
│ │          text=spec_text,                                   │  │
│ │          metadata={"test_cases": result}                  │  │
│ │      )                                                     │  │
│ └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

📊 סיכום תרחיש 2:
✅ FAISS משמש ל-semantic caching (מוצא specs דומים)
✅ Redis משמש ל-exact caching (hash של spec)
✅ FAISS מהיר יותר אבל פחות מדויק
✅ Redis איטי יותר אבל 100% מדויק
```

---

### תרחיש 3: צ'אט עם Weather/Time (ללא FAISS!)

```
┌─────────────────────────────────────────────────────────────────┐
│ USER: POST /chat                                                 │
│ Headers: user-id: alice                                          │
│ Body: {message: "What time is it in Israel?"}                   │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ Orchestrator.handle_chat()                                       │
│   → Router decides: "time_agent"                                 │
│   → Execute: TimeAgent.process({"message": "..."})               │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ TimeAgent.process()                                              │
│ (src/agents/time_agent.py)                                       │
│                                                                  │
│ ❌ אין שימוש ב-FAISS כאן!                                      │
│ ❌ אין שימוש ב-Redis cache!                                     │
│                                                                  │
│ ✅ רק קריאה ישירה ל-tool function                               │
│    get_current_time("Israel")                                    │
│    → returns time string                                         │
└─────────────────────────────────────────────────────────────────┘

📊 למה לא FAISS?
- Time/Weather הם real-time data
- אין טעם לקאש (הזמן משתנה כל שנייה)
- פשוט ומהיר ללא caching
```

---

## 🗃️ Redis - מה נשמר? איפה? מתי?

### Redis Structure במלואו:

```
Redis Database (localhost:6381)
│
├─ 🔑 session:{user_id}  ← User Session Data
│  │
│  ├─ session:alice
│  │  └─ {
│  │       "user_id": "alice",
│  │       "files": [
│  │         {
│  │           "name": "login_spec.pdf",
│  │           "type": "pdf",
│  │           "content": "Full specification text...",
│  │           "size": 12345
│  │         }
│  │       ],
│  │       "history": [],  ← כרגע לא משתמשים
│  │       "state": {}      ← כרגע לא משתמשים
│  │     }
│  │  TTL: 3600 seconds (1 hour)
│  │
│  └─ session:bob
│     └─ {...}
│
├─ 🔑 cache:test_cases:{hash}  ← Test Cases Cache
│  │
│  ├─ cache:test_cases:a1b2c3d4e5f6
│  │  └─ {
│  │       "test_cases": [
│  │         {
│  │           "id": "TC001",
│  │           "title": "Verify login with valid credentials",
│  │           "steps": [...],
│  │           "expected_result": "..."
│  │         },
│  │         {...}, {...}
│  │       ],
│  │       "total_count": 10,
│  │       "coverage_areas": ["Authentication", "UI"]
│  │     }
│  │  TTL: 3600 seconds
│  │
│  └─ cache:test_cases:9f8e7d6c5b4a
│     └─ {...}
│
└─ 🔑 cache:{custom_key}  ← Generic Cache (optional)
   │
   └─ cache:any_custom_key
      └─ {data: "..."}
      TTL: configurable
```

### מי כותב ל-Redis?

| מי | איפה בקוד | מה נשמר | מתי |
|---|---|---|---|
| **Orchestrator** | `orchestrator.py:266` | File info → `session:alice` | בעת העלאת קובץ |
| **SessionManager** | `session_manager.py:72` | Create session → `session:alice` | יצירת session חדש |
| **TestCaseAgent** | `test_case_agent.py:167` | Test cases → `cache:test_cases:xxx` | אחרי generation |

### מי קורא מ-Redis?

| מי | איפה בקוד | מה קורא | מתי |
|---|---|---|---|
| **Orchestrator** | `orchestrator.py:83` | Get session → `session:alice` | Initialize |
| **TestCaseAgent** | `test_case_agent.py:141` | Get cache → `cache:test_cases:xxx` | לפני generation |
| **API** | `api.py:117` | Get session → `session:alice` | GET /session/{user_id} |

---

## 💾 FAISS - מה נשמר? איפה? מתי?

### FAISS Structure (In-Memory):

```
FAISSService(user_id="alice")  ← Per User Instance
│
├─ 📊 self.index  ← FAISS Vector Index
│  │  Type: IndexFlatL2 (L2 distance)
│  │  Dimensions: 1536 (OpenAI ada-002)
│  │
│  ├─ Vector 0: [0.123, -0.456, 0.789, ..., 0.234]
│  │  └─> login_spec.pdf embedding
│  │
│  ├─ Vector 1: [-0.321, 0.654, -0.987, ..., 0.432]
│  │  └─> register_spec.pdf embedding
│  │
│  └─ Vector 2: [0.555, 0.111, -0.222, ..., -0.999]
│     └─> checkout_spec.pdf embedding
│
├─ 📄 self.documents  ← Original Text
│  │
│  ├─ [0]: "Login page specification:\n\nThe login page..."
│  ├─ [1]: "Registration form requirements:\n\n..."
│  └─ [2]: "Checkout process specification:\n\n..."
│
└─ 📋 self.metadata  ← Associated Data
   │
   ├─ [0]: {
   │      "file_name": "login_spec.pdf",
   │      "type": "specification",
   │      "test_cases": {  ← cached result!
   │          test_cases: [...],
   │          total_count: 10
   │      }
   │  }
   │
   ├─ [1]: {"file_name": "register_spec.pdf", ...}
   └─ [2]: {"file_name": "checkout_spec.pdf", ...}

❗ Important: All in RAM, lost on server restart!
```

### מי כותב ל-FAISS?

| מי | איפה בקוד | מה נשמר | מתי |
|---|---|---|---|
| **Orchestrator** | `orchestrator.py:270` | File text + metadata | בעת העלאת קובץ |
| **TestCaseAgent** | `test_case_agent.py:170` | Spec text + test_cases | אחרי generation |

### מי קורא מ-FAISS?

| מי | איפה בקוד | מה מחפש | מתי |
|---|---|---|---|
| **TestCaseAgent** | `test_case_agent.py:148` | Similar specs | לפני generation |

---

## 🔄 השוואה: Redis vs FAISS

### Redis (SessionManager)

```
מטרה: שמירה persistent של data
נפח: כל המידע (files, cache, sessions)
מהירות: בינונית (network I/O)
דיוק: 100% (exact match)
חיים: Persistent (שורד restart)
שיתוף: משותף בין users (מבודד לפי keys)

Use Cases:
✅ שמירת קבצים שהועלו
✅ cache של test cases (by hash)
✅ session data (history, state)
✅ כל מה שצריך לשרוד restart
```

### FAISS (FAISSService)

```
מטרה: חיפוש סמנטי מהיר
נפח: רק documents + embeddings
מהירות: מהירה מאוד (in-memory)
דיוק: ~85-95% (similarity)
חיים: In-memory (נמחק ב-restart)
שיתוף: אין! instance per user

Use Cases:
✅ מציאת specs דומים
✅ semantic caching
✅ deduplication
✅ חיפוש מהיר במסמכים
```

---

## 🎯 מתי משתמשים במה?

### Redis משמש:

1. **שמירת קבצים** (`Orchestrator.handle_file_upload` → line 266)
   ```python
   await session_manager.add_file_to_session(user_id, file_info)
   ```

2. **Cache של test cases** (`TestCaseAgent.process` → line 167)
   ```python
   cache_key = f"test_cases:{hash(spec_text)}"
   await self.set_cache(cache_key, result, ttl=3600)
   ```

3. **Query session** (`API.get_session` → api.py line 117)
   ```python
   session = await session_manager.get_session(user_id)
   ```

**סה"כ:** 3 מקומות קריאה ישירה

---

### FAISS משמש:

1. **שמירת file embedding** (`Orchestrator.handle_file_upload` → line 270)
   ```python
   self.faiss_service.add_document(text=text_content, metadata={...})
   ```

2. **חיפוש specs דומים** (`TestCaseAgent.process` → line 148)
   ```python
   similar = self.faiss_service.search(spec_text, top_k=1)
   ```

3. **שמירת spec + test_cases** (`TestCaseAgent.process` → line 170)
   ```python
   self.faiss_service.add_document(text=spec_text, metadata={"test_cases": result})
   ```

**סה"כ:** 3 מקומות קריאה ישירה

---

## 📊 Flow Diagram: Complete Storage Operations

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER REQUEST ARRIVES                          │
└────────────┬────────────────────────────────────────────────────┘
             │
             ├─────────────────┬────────────────────┐
             │                 │                    │
             ▼                 ▼                    ▼
      ┌───────────┐    ┌────────────┐     ┌─────────────┐
      │   /chat   │    │  /upload   │     │  /session   │
      └─────┬─────┘    └──────┬─────┘     └──────┬──────┘
            │                 │                    │
            ▼                 ▼                    ▼
    ┌──────────────┐  ┌─────────────────┐  ┌──────────────┐
    │handle_chat() │  │handle_file_    │  │get_session() │
    │              │  │upload()         │  │              │
    └───────┬──────┘  └────────┬────────┘  └──────┬───────┘
            │                  │                    │
            │                  │                    │
            ├──────────────────┼────────────────────┘
            │                  │
            ▼                  ▼
    ┌──────────────────────────────────────────┐
    │         Storage Decision                  │
    │                                           │
    │  Is it a file?                            │
    │    YES → Save to Redis + FAISS           │
    │                                           │
    │  Is it test case generation?              │
    │    YES → Check Redis → Check FAISS        │
    │           → Generate → Save both          │
    │                                           │
    │  Is it time/weather?                      │
    │    NO storage needed                      │
    └──────────┬───────────────────────────────┘
               │
               ├─────────────────────┬
               │                     │
               ▼                     ▼
        ┌─────────────┐      ┌─────────────┐
        │   REDIS     │      │   FAISS     │
        │  (Disk)     │      │  (Memory)   │
        └─────────────┘      └─────────────┘
               │                     │
               ├─────────────────────┤
               │                     │
               ▼                     ▼
        session:alice         alice's FAISS
        cache:test_cases:*    index + docs
```

---

## ❓ שאלות ותשובות

### ש: האם הצ'אט נשמר?
**תשובה:** לא כרגע! 

Redis session יש שדה `history: []` אבל הוא לא משמש.
אם רוצה לשמור צ'אט, צריך להוסיף:

```python
# In Orchestrator.handle_chat():
await session_manager.update_session(user_id, {
    "history": session.get("history", []) + [{
        "message": message,
        "response": result["response"],
        "timestamp": datetime.now().isoformat()
    }]
})
```

---

### ש: האם FAISS עובד בכל האייגנטים?
**תשובה:** לא!

- ✅ **TestCaseAgent** - כן (semantic caching)
- ❌ **WeatherAgent** - לא (real-time data)
- ❌ **TimeAgent** - לא (real-time data)

**למה?** כי Weather ו-Time לא צריכים חיפוש סמנטי או caching.

---

### ש: מה הטעם ב-FAISS אם יש Redis?
**תשובה:** semantic matching!

**דוגמה:**
- Redis: "login specification" ≠ "sign in requirements" (different hash)
- FAISS: "login specification" ≈ "sign in requirements" (similarity: 0.89)

FAISS מוצא מסמכים **דומים** גם אם הם לא זהים!

---

### ש: אם המערכת נכבית, מה קורה?
**תשובה:**

- ✅ **Redis:** כל המידע נשאר (persistent)
- ❌ **FAISS:** כל המידע נמחק (in-memory)

כש-server מתניע מחדש:
1. Redis sessions עדיין קיימים
2. FAISS indexes ריקים
3. צריך להעלות קבצים מחדש כדי לבנות FAISS

---

### ש: האם אליס רואה את ה-FAISS של בוב?
**תשובה:** לא! מבודדים לחלוטין.

```python
alice_orchestrator = Orchestrator("alice")
alice_orchestrator.faiss_service  # ← Alice's FAISS

bob_orchestrator = Orchestrator("bob")
bob_orchestrator.faiss_service    # ← Bob's FAISS

# שני instances נפרדים!
```

---

## 🎓 סיכום: מי עושה מה?

### Orchestrator:
- ✅ יוצר FAISS instance (per user)
- ✅ משתמש ב-Redis (shared singleton)
- ✅ שומר קבצים ב-Redis + FAISS
- ✅ מעביר FAISS reference ל-TestCaseAgent

### TestCaseAgent:
- ✅ מקבל FAISS reference מ-Orchestrator
- ✅ מחפש ב-FAISS (semantic search)
- ✅ מחפש ב-Redis (exact cache)
- ✅ שומר ב-FAISS + Redis אחרי generation

### WeatherAgent / TimeAgent:
- ❌ לא משתמשים ב-FAISS
- ❌ לא משתמשים ב-Redis cache
- ✅ רק קריאה ישירה ל-tools

---

**סוף המסמך המפורט! 🎯**
