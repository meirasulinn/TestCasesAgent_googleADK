# Redis + FAISS + Cache Architecture - Complete Deep Dive

## 🏗️ System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STORAGE & CACHE ARCHITECTURE                             │
│                                                                             │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────┐ │
│  │   REDIS (Global)     │  │  FAISS (Per-User)    │  │   ADK Sessions   │ │
│  │   SessionManager     │  │   FAISSService       │  │ InMemorySession  │ │
│  ├──────────────────────┤  ├──────────────────────┤  ├──────────────────┤ │
│  │ • User sessions      │  │ • Vector search      │  │ • Agent runtime  │ │
│  │ • File metadata      │  │ • Embeddings         │  │ • Conversation   │ │
│  │ • Test case cache    │  │ • Similarity search  │  │ • Context        │ │
│  │ • Persistent         │  │ • In-memory          │  │ • Ephemeral      │ │
│  │ • Shared             │  │ • Per-user isolation │  │ • Per-session    │ │
│  └──────────────────────┘  └──────────────────────┘  └──────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔴 REDIS - The Global State Manager

### 📋 Role & Responsibilities:

**תפקיד ראשי:** ניהול state גלובלי ומתמשך (persistent) של כל המשתמשים

**מי מנהל:** `SessionManager` (singleton instance) - `src/services/session_manager.py`

### 🗂️ Redis Key Structure:

```
Redis Database (Docker localhost:6381)
│
├─ 1️⃣ USER SESSIONS (Global, Per-User, Persistent)
│  │
│  ├─ session:alice
│  │  └─ {
│  │       "user_id": "alice",
│  │       "created_at": "2025-11-25T10:00:00Z",
│  │       "updated_at": "2025-11-25T10:30:00Z",
│  │       "files": [
│  │         {
│  │           "name": "login_spec.pdf",
│  │           "type": "pdf",
│  │           "content": "Full specification text...",
│  │           "size": 45678,
│  │           "uploaded_at": "2025-11-25T10:05:00Z"
│  │         },
│  │         {
│  │           "name": "register_spec.pdf",
│  │           "type": "pdf",
│  │           "content": "Registration form spec...",
│  │           "size": 32145,
│  │           "uploaded_at": "2025-11-25T10:15:00Z"
│  │         }
│  │       ],
│  │       "stats": {
│  │         "total_files": 2,
│  │         "total_requests": 15
│  │       }
│  │     }
│  │  
│  ├─ session:bob
│  │  └─ {
│  │       "user_id": "bob",
│  │       "created_at": "2025-11-25T11:00:00Z",
│  │       "updated_at": "2025-11-25T11:20:00Z",
│  │       "files": [
│  │         {
│  │           "name": "payment_spec.docx",
│  │           "type": "docx",
│  │           "content": "Payment flow specification...",
│  │           "size": 28900,
│  │           "uploaded_at": "2025-11-25T11:10:00Z"
│  │         }
│  │       ],
│  │       "stats": {
│  │         "total_files": 1,
│  │         "total_requests": 5
│  │       }
│  │     }
│  │
│  └─ session:charlie
│     └─ {...}
│
│
├─ 2️⃣ TEST CASE CACHE (Global, Shared by Hash, TTL=1h)
│  │
│  ├─ test_cases:a1b2c3d4e5f6
│  │  └─ {
│  │       "test_cases": [
│  │         {
│  │           "id": "TC001",
│  │           "title": "Verify login with valid credentials",
│  │           "priority": "high",
│  │           "steps": ["Navigate to login", "Enter username", "Enter password"],
│  │           "expected_result": "User logged in successfully",
│  │           "tags": ["authentication", "happy-path"]
│  │         },
│  │         {...}, {...}
│  │       ],
│  │       "total_count": 10,
│  │       "coverage_areas": ["Authentication", "UI", "Security"],
│  │       "generated_at": "2025-11-25T10:05:30Z",
│  │       "spec_hash": "a1b2c3d4e5f6"
│  │     }
│  │  TTL: 3600 seconds (expires after 1 hour)
│  │
│  ├─ test_cases:9f8e7d6c5b4a
│  │  └─ {...}
│  │  TTL: 3600 seconds
│  │
│  └─ test_cases:1a2b3c4d5e6f
│     └─ {...}
│     TTL: 3600 seconds
│
│
└─ 3️⃣ GENERIC CACHE (Optional, Configurable TTL)
   │
   ├─ cache:api_response_xyz
   │  └─ {...}
   │  TTL: Custom
   │
   └─ cache:config_data
      └─ {...}
      TTL: Custom
```

---

## 🟢 FAISS - The Semantic Search Engine

### 📋 Role & Responsibilities:

**תפקיד ראשי:** חיפוש סמנטי (semantic search) של מסמכים דומים באמצעות vector embeddings

**מי מנהל:** `FAISSService` - instance נפרד **לכל user** - `src/services/faiss_service.py`

### 🔍 FAISS Architecture (Per-User Instance):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FAISSService(user_id="alice")                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Component 1: FAISS Index (Vector Database)                                │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │ self.index = faiss.IndexFlatL2(1536)                              │    │
│  │                                                                    │    │
│  │ Purpose: Stores document embeddings as high-dimensional vectors   │    │
│  │                                                                    │    │
│  │ Structure:                                                         │    │
│  │   Vector 0: [0.123, -0.456, 0.789, ..., 0.234]  ← login_spec.pdf │    │
│  │   Vector 1: [-0.321, 0.654, -0.987, ..., 0.432] ← register.pdf   │    │
│  │   Vector 2: [0.555, 0.111, -0.222, ..., -0.999] ← checkout.pdf   │    │
│  │   ...                                                              │    │
│  │                                                                    │    │
│  │ Dimensions: 1536 (OpenAI text-embedding-ada-002)                  │    │
│  │ Algorithm: L2 distance (Euclidean)                                │    │
│  │ Speed: O(n) for flat index, very fast for small datasets         │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  Component 2: Documents List (Original Text)                               │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │ self.documents: List[str] = [                                     │    │
│  │   "Login page specification:\n\nThe login page allows...",  ← [0]│    │
│  │   "Registration form requirements:\n\nThe form includes...", ← [1]│    │
│  │   "Checkout process specification:\n\nUser selects...",     ← [2]│    │
│  │   ...                                                              │    │
│  │ ]                                                                  │    │
│  │                                                                    │    │
│  │ Purpose: Store original text for retrieval                        │    │
│  │ Index: Matches FAISS vector index (document[i] → vector[i])      │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  Component 3: Metadata List (File Information)                             │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │ self.metadata: List[Dict] = [                                     │    │
│  │   {                                                          ← [0]│    │
│  │     "file_name": "login_spec.pdf",                                │    │
│  │     "type": "specification",                                      │    │
│  │     "uploaded_at": "2025-11-25T10:05:00Z",                        │    │
│  │     "test_cases": {...}  ← Optional cached result                │    │
│  │   },                                                               │    │
│  │   {                                                          ← [1]│    │
│  │     "file_name": "register_spec.pdf",                             │    │
│  │     "type": "specification",                                      │    │
│  │     "uploaded_at": "2025-11-25T10:15:00Z",                        │    │
│  │     "test_cases": {...}                                           │    │
│  │   },                                                               │    │
│  │   ...                                                              │    │
│  │ ]                                                                  │    │
│  │                                                                    │    │
│  │ Purpose: Store metadata for context and caching                   │    │
│  │ Index: Matches FAISS vector index (metadata[i] → vector[i])      │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  Properties:                                                                │
│  • In-Memory: Lost on server restart                                       │
│  • Per-User: alice's FAISS ≠ bob's FAISS                                  │
│  • Fast: Similarity search in milliseconds                                 │
│  • Isolated: No cross-user contamination                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                    FAISSService(user_id="bob")                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  self.index = faiss.IndexFlatL2(1536)   ← Separate index                  │
│  self.documents = [...]                  ← Bob's documents only            │
│  self.metadata = [...]                   ← Bob's metadata only             │
│                                                                             │
│  ⚠️ Completely isolated from Alice's FAISS!                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔵 ADK Sessions (InMemorySessionService)

### 📋 Role & Responsibilities:

**תפקיד ראשי:** ניהול conversation context ו-runtime state של agents במהלך ביצוע

**מי מנהל:** `InMemorySessionService` - instance ב-**כל agent** - מובנה ב-Google ADK

### 🔄 ADK Session Structure:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    InMemorySessionService Architecture                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User: alice                                                                │
│  │                                                                           │
│  ├─ Router Agent Session                                                    │
│  │  ┌────────────────────────────────────────────────────────────────┐    │
│  │  │ app_name: "orchestrator_router_alice"                          │    │
│  │  │ session_id: "router_session_12345"  ← Stored in Orchestrator   │    │
│  │  │                                                                 │    │
│  │  │ Messages History:                                               │    │
│  │  │   [                                                             │    │
│  │  │     {"role": "user", "content": "What time is it in Israel?"},│    │
│  │  │     {"role": "assistant", "content": "time_agent"},            │    │
│  │  │     {"role": "user", "content": "What's the weather in NY?"},  │    │
│  │  │     {"role": "assistant", "content": "weather_agent"},         │    │
│  │  │     ...                                                         │    │
│  │  │   ]                                                             │    │
│  │  │                                                                 │    │
│  │  │ Context: Routing decisions history                             │    │
│  │  │ Lifetime: Exists while Orchestrator exists                     │    │
│  │  └────────────────────────────────────────────────────────────────┘    │
│  │                                                                           │
│  ├─ TestCaseAgent Sessions                                                  │
│  │  ┌────────────────────────────────────────────────────────────────┐    │
│  │  │ app_name: "test_case_generator"                                │    │
│  │  │ session_id: "gen_alice_a1b2c3d4"  ← Created per generation     │    │
│  │  │                                                                 │    │
│  │  │ Messages History:                                               │    │
│  │  │   [                                                             │    │
│  │  │     {"role": "user", "content": "Generate test cases for..."},│    │
│  │  │     {"role": "assistant", "content": "Here are 10 test..."},   │    │
│  │  │     ...                                                         │    │
│  │  │   ]                                                             │    │
│  │  │                                                                 │    │
│  │  │ Context: Spec text, previous generations                       │    │
│  │  │ Lifetime: Created per generation, ephemeral                    │    │
│  │  └────────────────────────────────────────────────────────────────┘    │
│  │                                                                           │
│  ├─ WeatherAgent Sessions                                                   │
│  │  ┌────────────────────────────────────────────────────────────────┐    │
│  │  │ app_name: "weather_agent"                                      │    │
│  │  │ session_id: "weather_alice_5678"  ← Created per request        │    │
│  │  │                                                                 │    │
│  │  │ Messages History:                                               │    │
│  │  │   [                                                             │    │
│  │  │     {"role": "user", "content": "What's the weather in NY?"}, │    │
│  │  │     {"role": "assistant", "content": "Weather in NY: Sunny..."}, │  │
│  │  │     ...                                                         │    │
│  │  │   ]                                                             │    │
│  │  │                                                                 │    │
│  │  │ Tool Calls: [get_weather("New York")]                          │    │
│  │  │ Lifetime: Created per request, ephemeral                       │    │
│  │  └────────────────────────────────────────────────────────────────┘    │
│  │                                                                           │
│  └─ TimeAgent Sessions                                                      │
│     ┌────────────────────────────────────────────────────────────────┐    │
│     │ app_name: "time_agent"                                         │    │
│     │ session_id: "time_alice_9012"  ← Created per request           │    │
│     │                                                                 │    │
│     │ Messages History:                                               │    │
│     │   [                                                             │    │
│     │     {"role": "user", "content": "What time is it in Israel?"}, │    │
│     │     {"role": "assistant", "content": "Current time in..."} ,   │    │
│     │     ...                                                         │    │
│     │   ]                                                             │    │
│     │                                                                 │    │
│     │ Tool Calls: [get_current_time("Israel")]                       │    │
│     │ Lifetime: Created per request, ephemeral                       │    │
│     └────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  Properties:                                                                │
│  • In-Memory: Not persisted to disk                                        │
│  • Per-Agent: Each agent has its own InMemorySessionService                │
│  • Conversation Context: Maintains message history for context             │
│  • Ephemeral: Lost on server restart                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Complete Data Flow with All Variations

### Variation 1️⃣: First-Time File Upload (Cold Start)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ SCENARIO: Alice uploads "login_spec.pdf" for the first time                │
└─────────────────────────────────────────────────────────────────────────────┘

Step 1: User uploads file
  │
  ▼
┌────────────────────────────────────────────────────────────────────┐
│ API: POST /upload                                                  │
│ Header: user-id: alice                                             │
│ Body: {file: login_spec.pdf}                                       │
└────────────────────┬───────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│ get_orchestrator("alice")                                          │
│   └─> Check _orchestrators["alice"]                                │
│       ├─ Not exists → Create new Orchestrator("alice")            │
│       │   ├─> self.faiss_service = FAISSService("alice") ◄─ NEW! │
│       │   └─> await initialize()                                   │
│       │        └─> SessionManager.get_session("alice")             │
│       │            ├─ Redis.get("session:alice") → None           │
│       │            └─> SessionManager.create_session("alice")      │
│       │                 └─> Redis.set("session:alice", {...})     │
│       │                                                             │
│       └─> Return orchestrator                                      │
└────────────────────┬───────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│ Orchestrator.handle_file_upload()                                  │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │ STEP 1: Parse file                                          │  │
│ │   text_content = "Login page specification: ..."           │  │
│ └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │ STEP 2: Add to Redis                                        │  │
│ │   SessionManager.add_file_to_session("alice", file_info)   │  │
│ │     ├─> Redis.get("session:alice") → Get current session   │  │
│ │     ├─> session_data["files"].append(file_info)            │  │
│ │     └─> Redis.set("session:alice", updated_session)        │  │
│ │                                                              │  │
│ │   Redis State After:                                        │  │
│ │   session:alice → {                                         │  │
│ │     files: [{name: "login_spec.pdf", content: "...", ...}] │  │
│ │   }                                                          │  │
│ └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │ STEP 3: Add to FAISS                                        │  │
│ │   FAISSService.add_document(text_content, metadata)        │  │
│ │     ├─> OpenAI.create_embedding(text_content)              │  │
│ │     │   └─> Returns: [0.123, -0.456, ..., 0.234] (1536)   │  │
│ │     ├─> vector = np.array([embedding])                     │  │
│ │     ├─> self.index.add(vector)  ◄─ Add to FAISS           │  │
│ │     ├─> self.documents.append(text_content)                │  │
│ │     └─> self.metadata.append(metadata)                     │  │
│ │                                                              │  │
│ │   FAISS State After (alice):                                │  │
│ │   index: [Vector0]                                          │  │
│ │   documents: ["Login page specification..."]               │  │
│ │   metadata: [{"file_name": "login_spec.pdf", ...}]        │  │
│ └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │ STEP 4: Auto-generate test cases via routing               │  │
│ │   handle_chat("Generate test cases for [spec]...")         │  │
│ │     ├─> Router Agent → "test_case_agent"                   │  │
│ │     └─> TestCaseAgent.process({"spec": spec_text})         │  │
│ └─────────────────────────────────────────────────────────────┘  │
└────────────────────┬───────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│ TestCaseAgent.process()                                            │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │ CACHE CHECK 1: Redis cache                                  │  │
│ │   cache_key = f"test_cases:{hash(spec_text)}"               │  │
│ │   cached = SessionManager.get_cache(cache_key)              │  │
│ │     └─> Redis.get("test_cases:a1b2c3d4") → None ❌         │  │
│ └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │ CACHE CHECK 2: FAISS similarity                             │  │
│ │   similar = FAISSService.search(spec_text, top_k=3)        │  │
│ │     ├─> OpenAI.create_embedding(spec_text)                  │  │
│ │     ├─> query_vector = [...]                                │  │
│ │     ├─> distances, indices = index.search(query_vector, 3) │  │
│ │     └─> Returns: [] (empty, no similar docs yet) ❌        │  │
│ └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │ GENERATE: No cache, generate with ADK                       │  │
│ │   _generate_with_adk(spec_text)                             │  │
│ │     ├─> Create ADK session:                                 │  │
│ │     │   session_id = "gen_alice_a1b2c3d4"                   │  │
│ │     │   InMemorySessionService.create_session(...)          │  │
│ │     │                                                        │  │
│ │     ├─> Create Runner                                        │  │
│ │     ├─> runner.run_async(...)                               │  │
│ │     │   ├─> LlmAgent processes spec                         │  │
│ │     │   ├─> OpenAI API call (gpt-4o-mini)                   │  │
│ │     │   └─> Returns JSON with test cases                    │  │
│ │     │                                                        │  │
│ │     └─> Parse response → result = {                         │  │
│ │           test_cases: [...10 test cases...],                │  │
│ │           total_count: 10,                                   │  │
│ │           coverage_areas: [...]                             │  │
│ │         }                                                    │  │
│ └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │ CACHE SAVE 1: Store in Redis                                │  │
│ │   SessionManager.set_cache(cache_key, result, ttl=3600)    │  │
│ │     └─> Redis.setex("test_cases:a1b2c3d4", 3600, result)   │  │
│ │                                                              │  │
│ │   Redis State After:                                        │  │
│ │   test_cases:a1b2c3d4 → {test_cases: [...], ...}          │  │
│ │   TTL: 3600 seconds                                         │  │
│ └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │ CACHE SAVE 2: Update FAISS metadata (optional)              │  │
│ │   metadata[0]["test_cases"] = result                        │  │
│ │   (For future similarity searches)                          │  │
│ └─────────────────────────────────────────────────────────────┘  │
└────────────────────┬───────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│ Return to User                                                      │
│ {                                                                   │
│   "response": "File uploaded successfully. Generated 10 test cases",│
│   "test_cases": [...],                                             │
│   "agent_used": "test_case_agent"                                  │
│ }                                                                   │
└────────────────────────────────────────────────────────────────────┘

FINAL STATE:
├─ Redis: session:alice → {files: [login_spec.pdf]}
├─ Redis: test_cases:a1b2c3d4 → {test_cases: [...]} (TTL: 3600s)
├─ FAISS (alice): 1 document with embedding
└─ ADK Session: gen_alice_a1b2c3d4 (ephemeral, will be garbage collected)
```

---

### Variation 2️⃣: Second File Upload (Warm Start - Redis Cache Hit)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ SCENARIO: Alice uploads the SAME "login_spec.pdf" again (or identical content)│
└─────────────────────────────────────────────────────────────────────────────┘

Step 1-3: Same as Variation 1 (file parsed, added to Redis session, added to FAISS)

Step 4: TestCaseAgent.process()
  │
  ▼
┌────────────────────────────────────────────────────────────────────┐
│ CACHE CHECK 1: Redis cache                                        │
│   cache_key = f"test_cases:{hash(spec_text)}"  # Same hash!       │
│   cached = SessionManager.get_cache(cache_key)                    │
│     └─> Redis.get("test_cases:a1b2c3d4") → {...} ✅ HIT!         │
│                                                                     │
│   Returns immediately: {                                           │
│     test_cases: [...],                                             │
│     total_count: 10,                                               │
│     source: "redis_cache"  ← Indicates cache hit                  │
│   }                                                                │
│                                                                     │
│ ⚡ SKIPPED: FAISS search                                           │
│ ⚡ SKIPPED: ADK generation                                         │
│ ⚡ FAST: Response in ~10ms instead of ~5000ms                      │
└────────────────────────────────────────────────────────────────────┘

BENEFIT: Saved API call to OpenAI, instant response!
```

---

### Variation 3️⃣: Similar Specification Upload (FAISS Cache Hit)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ SCENARIO: Alice uploads "register_spec.pdf" - similar to login spec        │
│           (Both about authentication, similar content)                      │
└─────────────────────────────────────────────────────────────────────────────┘

Step 1-3: File parsed, added to Redis session, added to FAISS (now has 2 docs)

Step 4: TestCaseAgent.process()
  │
  ▼
┌────────────────────────────────────────────────────────────────────┐
│ CACHE CHECK 1: Redis cache                                        │
│   cache_key = f"test_cases:{hash(spec_text)}"  # Different hash   │
│   cached = SessionManager.get_cache(cache_key)                    │
│     └─> Redis.get("test_cases:9f8e7d6c") → None ❌ MISS          │
└────────────────────┬───────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│ CACHE CHECK 2: FAISS similarity                                    │
│   similar = FAISSService.search(spec_text, top_k=3)               │
│     ├─> OpenAI.create_embedding(spec_text)                         │
│     │   └─> query_vector = [0.125, -0.460, ...]                   │
│     │                                                               │
│     ├─> index.search(query_vector, k=3)                            │
│     │   └─> Finds: Vector0 (login_spec.pdf)                        │
│     │       distance: 0.05 → similarity: 0.95 ✅ VERY SIMILAR!    │
│     │                                                               │
│     └─> Returns: [                                                 │
│           {                                                         │
│             "document": "Login page specification...",             │
│             "metadata": {                                          │
│               "file_name": "login_spec.pdf",                       │
│               "test_cases": {...}  ← Has cached test cases!       │
│             },                                                      │
│             "similarity": 0.95                                     │
│           }                                                         │
│         ]                                                          │
│                                                                     │
│   Check similarity threshold (0.85):                                │
│     if 0.95 > 0.85 AND metadata has test_cases:                   │
│       Return cached test_cases ✅                                  │
│                                                                     │
│ ⚡ SKIPPED: ADK generation                                         │
│ ⚡ SMART: Reused similar spec's test cases                         │
└────────────────────────────────────────────────────────────────────┘

BENEFIT: Semantic caching - found similar spec without exact match!
```

---

### Variation 4️⃣: Different User (Isolation Test)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ SCENARIO: Bob uploads the SAME "login_spec.pdf" as Alice                   │
└─────────────────────────────────────────────────────────────────────────────┘

Step 1: get_orchestrator("bob")
  │
  ▼
┌────────────────────────────────────────────────────────────────────┐
│ Check _orchestrators["bob"] → Not exists                          │
│ Create new Orchestrator("bob")                                     │
│   ├─> self.faiss_service = FAISSService("bob") ◄─ NEW INSTANCE!  │
│   │   (Separate from alice's FAISS!)                              │
│   │                                                                 │
│   └─> SessionManager.get_session("bob")                           │
│       └─> Redis.get("session:bob") → None                         │
│           └─> Create Redis session                                │
│               └─> Redis.set("session:bob", {...})                 │
└────────────────────┬───────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│ File added to Redis:                                               │
│   session:bob → {files: [{name: "login_spec.pdf", ...}]}         │
│                                                                     │
│ File added to FAISS:                                                │
│   FAISSService(bob).index: [Vector0] ← Bob's vector               │
│   (Isolated from alice's FAISS!)                                   │
└────────────────────┬───────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│ TestCaseAgent.process()                                            │
│                                                                     │
│ CACHE CHECK 1: Redis cache                                        │
│   cache_key = f"test_cases:{hash(spec_text)}"  # Same hash as Alice!│
│   cached = SessionManager.get_cache(cache_key)                    │
│     └─> Redis.get("test_cases:a1b2c3d4") → {...} ✅ HIT!         │
│                                                                     │
│   Returns Alice's cached test cases!                               │
│   (This is OK - same spec, same test cases)                       │
│                                                                     │
│ ⚠️ NOTE: Bob can access test case CACHE (by hash)                 │
│ ✅ BUT: Bob CANNOT access alice's session or FAISS                │
└────────────────────────────────────────────────────────────────────┘

ISOLATION:
├─ ✅ session:alice ≠ session:bob (separate Redis keys)
├─ ✅ FAISSService(alice) ≠ FAISSService(bob) (separate instances)
├─ ⚠️ test_cases:xxx (shared by hash - OK for efficiency)
└─ ✅ Orchestrator(alice) ≠ Orchestrator(bob) (separate instances)
```

---

### Variation 5️⃣: Chat Request (No File Upload)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ SCENARIO: Alice sends chat message: "What time is it in Israel?"           │
└─────────────────────────────────────────────────────────────────────────────┘

Step 1: POST /chat
  │
  ▼
┌────────────────────────────────────────────────────────────────────┐
│ get_orchestrator("alice")                                          │
│   └─> Returns existing orchestrator (already initialized)          │
└────────────────────┬───────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│ Orchestrator.handle_chat("What time is it in Israel?")            │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │ STEP 1: Route with Router Agent                             │  │
│ │   _route_to_agent(message)                                  │  │
│ │     ├─> Use stored router_session_id                        │  │
│ │     ├─> router_runner.run_async(...)                        │  │
│ │     │   ├─> LlmAgent analyzes: "time...Israel"             │  │
│ │     │   └─> Returns: "time_agent"                           │  │
│ │     └─> Validate agent exists                               │  │
│ │                                                              │  │
│ │   ADK Session Used:                                         │  │
│ │   session_id: "router_session_12345" (persistent)          │  │
│ │   InMemorySessionService stores conversation               │  │
│ └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │ STEP 2: Execute TimeAgent                                   │  │
│ │   TimeAgent.process({"message": "What time is it..."})     │  │
│ └─────────────────────────────────────────────────────────────┘  │
└────────────────────┬───────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│ TimeAgent.process()                                                │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────┐  │
│ │ Create ADK session for this request:                        │  │
│ │   session_id = "time_alice_5678"  ← Ephemeral              │  │
│ │   InMemorySessionService.create_session(...)                │  │
│ │                                                              │  │
│ │ Create Runner:                                               │  │
│ │   runner = Runner(agent=self.adk_agent, ...)               │  │
│ │                                                              │  │
│ │ Run agent:                                                   │  │
│ │   async for event in runner.run_async(...):                │  │
│ │     ├─> LlmAgent analyzes message                           │  │
│ │     ├─> Decides to call tool: get_current_time("Israel")   │  │
│ │     ├─> Tool executes:                                      │  │
│ │     │   └─> get_current_time("Israel")                      │  │
│ │     │       ├─> now = datetime.now(UTC)                     │  │
│ │     │       ├─> Add offset (+2 for Israel)                  │  │
│ │     │       └─> Return: "Current time in Israel: 09:45 PM..."│ │
│ │     │                                                        │  │
│ │     └─> LlmAgent formats response                           │  │
│ │         └─> "The current time in Israel is 09:45 PM..."    │  │
│ │                                                              │  │
│ │ Collect response and return                                 │  │
│ └─────────────────────────────────────────────────────────────┘  │
└────────────────────┬───────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│ Return to User                                                      │
│ {                                                                   │
│   "response": "The current time in Israel is 09:45 PM...",        │
│   "agent_used": "time_agent"                                       │
│ }                                                                   │
└────────────────────────────────────────────────────────────────────┘

STORAGE ACCESSED:
├─ Redis: ❌ None (no file, no cache)
├─ FAISS: ❌ None (no semantic search needed)
└─ ADK Sessions: ✅ router_session + time_session (ephemeral)
```

---

## 📊 Storage Comparison Matrix

| Feature | Redis (SessionManager) | FAISS (FAISSService) | ADK Sessions (InMemorySessionService) |
|---------|------------------------|----------------------|--------------------------------------|
| **Purpose** | Persistent state & cache | Semantic search | Runtime conversation context |
| **Scope** | Global (all users) | Per-user instance | Per-agent, per-request |
| **Lifetime** | Persistent (survives restart) | In-memory (lost on restart) | Ephemeral (garbage collected) |
| **Isolation** | By key prefix (session:user_id) | Separate instance per user | Separate per agent execution |
| **Shared?** | Test case cache shared by hash | ❌ Never shared | ❌ Never shared |
| **Speed** | Fast (network I/O) | Very fast (memory) | Very fast (memory) |
| **Size Limit** | Redis memory limit | System RAM | System RAM |
| **Use Cases** | - User sessions<br>- File metadata<br>- Test case cache | - Similar doc search<br>- Deduplication<br>- Smart caching | - Agent conversations<br>- Tool call history<br>- Context window |

---

## 🎯 Summary: Who Manages What?

```
┌──────────────────────────────────────────────────────────────┐
│                     MANAGEMENT HIERARCHY                      │
└──────────────────────────────────────────────────────────────┘

SessionManager (Singleton)
  │
  ├─> Manages: Redis connection
  ├─> Scope: Global (all users)
  ├─> Operations:
  │   ├─ create_session(user_id)
  │   ├─ get_session(user_id)
  │   ├─ add_file_to_session(user_id, file_info)
  │   ├─ get_cache(key)
  │   └─ set_cache(key, value, ttl)
  │
  └─> Storage Keys:
      ├─ session:{user_id} → User session data
      ├─ test_cases:{hash} → Test case cache (TTL: 3600s)
      └─ cache:{key} → Generic cache

Orchestrator (Per-User Instance)
  │
  ├─> Manages: User workflow coordination
  ├─> Scope: One per user
  ├─> Contains:
  │   ├─ FAISSService(user_id) ◄─ Per-user
  │   ├─ SessionManager (shared singleton)
  │   ├─ Router Agent + Session
  │   └─ Specialized Agents (TestCase, Weather, Time)
  │
  └─> Operations:
      ├─ handle_file_upload()
      ├─ handle_chat()
      └─ _route_to_agent()

FAISSService (Per-User Instance)
  │
  ├─> Manages: Semantic search for specific user
  ├─> Scope: One per user
  ├─> Components:
  │   ├─ index: faiss.IndexFlatL2(1536)
  │   ├─ documents: List[str]
  │   └─ metadata: List[Dict]
  │
  └─> Operations:
      ├─ add_document(text, metadata)
      ├─ search(query, top_k)
      └─ size()

InMemorySessionService (Per-Agent, Per-Request)
  │
  ├─> Manages: Agent runtime context
  ├─> Scope: Per agent execution
  ├─> Contains:
  │   ├─ Message history
  │   ├─ Tool call logs
  │   └─ Conversation context
  │
  └─> Operations:
      ├─ create_session(app_name, user_id, session_id)
      ├─ list_sessions(app_name, user_id)
      └─ get_session(session_id)
```

---

**Generated**: 2025-11-25  
**Branch**: new_version_adk_check_routing_orchestrator  
**File**: FAISS_REDIS_ARCHITECTURE.md
