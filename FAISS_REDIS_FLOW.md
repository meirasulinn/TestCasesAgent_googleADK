# FAISS + Redis Session Management - Complete Workflow

## 🗄️ Storage Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STORAGE LAYERS                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────┐     ┌──────────────────────────────────┐   │
│  │   REDIS (Global)          │     │   FAISS (Per-User)               │   │
│  │   Port: 6381              │     │   In-Memory Vector Index         │   │
│  ├───────────────────────────┤     ├──────────────────────────────────┤   │
│  │ • User sessions           │     │ • Document embeddings            │   │
│  │ • File metadata           │     │ • Semantic search                │   │
│  │ • Test case cache         │     │ • Per-user isolation             │   │
│  │ • Persistent across       │     │ • Lost on restart                │   │
│  │   restarts                │     │ • Fast similarity search         │   │
│  └───────────────────────────┘     └──────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Redis Storage Structure

### Keys and Data:

```
Redis Database (localhost:6381)
│
├─ session:{user_id}              ← User session data
│  │
│  └─ Value: {
│       "user_id": "user123",
│       "created_at": "2025-11-25T10:00:00",
│       "updated_at": "2025-11-25T10:05:00",
│       "files": [
│         {
│           "name": "login_spec.pdf",
│           "type": "pdf",
│           "content": "Full text content...",
│           "size": 45678,
│           "uploaded_at": "2025-11-25T10:05:00"
│         }
│       ]
│     }
│
├─ test_cases:{hash(spec_text)}   ← Test case cache
│  │
│  └─ Value: {
│       "test_cases": [
│         {
│           "id": "TC001",
│           "title": "Verify login with valid credentials",
│           ...
│         }
│       ],
│       "total_count": 10,
│       "coverage_areas": ["Authentication", "UI", ...]
│     }
│     TTL: 3600 seconds (1 hour)
│
└─ cache:{custom_key}             ← Generic cache (optional)
   │
   └─ Value: Any JSON data
      TTL: Configurable
```

---

## 🔍 FAISS Index Structure (Per User)

```
FAISSService Instance (user_id="user123")
│
├─ self.index = faiss.IndexFlatL2(1536)  ← Vector index (1536 dimensions)
│  │
│  └─ Stores: Document embeddings as vectors
│     Example: [0.123, -0.456, 0.789, ..., 0.234]  (1536 numbers)
│
├─ self.documents = []                   ← Original text
│  │
│  └─ List of document texts:
│     [
│       "Login page specification: The user enters...",
│       "Registration form requirements: The form should..."
│     ]
│
└─ self.metadata = []                    ← Document metadata
   │
   └─ List of metadata dicts:
     [
       {"file_name": "login_spec.pdf", "type": "specification"},
       {"file_name": "register_spec.pdf", "type": "specification"}
     ]
```

---

## 🔄 Complete Flow: File Upload → Storage

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    USER UPLOADS FILE                                       │
│             POST /upload + PDF file + user-id: "user123"                   │
└────────────────────────────┬───────────────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ FastAPI Endpoint (src/api/api.py)                                         │
│ ┌────────────────────────────────────────────────────────────────────┐   │
│ │ @app.post("/upload")                                               │   │
│ │ async def upload_file(file, user_id):                              │   │
│ │   orchestrator = await get_orchestrator(user_id)  ◄────┐          │   │
│ │   return await orchestrator.handle_file_upload(...)     │          │   │
│ └─────────────────────────────────────────────────────────┼──────────┘   │
└───────────────────────────────────────────────────────────┼────────────────┘
                                                            │
                                                            ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ get_orchestrator(user_id) - Global Registry                               │
│ ┌────────────────────────────────────────────────────────────────────┐   │
│ │ _orchestrators: Dict[str, Orchestrator] = {}  ◄── Global dict      │   │
│ │                                                                     │   │
│ │ if "user123" not in _orchestrators:                                │   │
│ │   orchestrator = Orchestrator("user123")                           │   │
│ │   await orchestrator.initialize()  ◄──┐                            │   │
│ │   _orchestrators["user123"] = orchestrator                         │   │
│ │                                       │                             │   │
│ │ return _orchestrators["user123"]     │                             │   │
│ └──────────────────────────────────────┼─────────────────────────────┘   │
└────────────────────────────────────────┼───────────────────────────────────┘
                                         │
                                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ Orchestrator.__init__(user_id="user123")                                  │
│ ┌────────────────────────────────────────────────────────────────────┐   │
│ │ self.user_id = "user123"                                           │   │
│ │ self.session_manager = session_manager  ◄── Singleton instance     │   │
│ │ self.faiss_service = FAISSService("user123")  ◄──┐                 │   │
│ │ self.agents = {}                                 │                 │   │
│ └──────────────────────────────────────────────────┼─────────────────┘   │
└────────────────────────────────────────────────────┼───────────────────────┘
                                                     │
                                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ FAISSService.__init__(user_id="user123")                                  │
│ (src/services/faiss_service.py)                                           │
│ ┌────────────────────────────────────────────────────────────────────┐   │
│ │ self.user_id = "user123"                                           │   │
│ │ self.dimension = 1536  ← OpenAI embedding dimension                │   │
│ │ self.index = faiss.IndexFlatL2(1536)  ← Create FAISS index        │   │
│ │ self.documents = []                                                │   │
│ │ self.metadata = []                                                 │   │
│ │                                                                     │   │
│ │ logger.info("FAISSService initialized for user user123")           │   │
│ └────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
              ORCHESTRATOR INITIALIZED (user123 has FAISS + Redis)
═══════════════════════════════════════════════════════════════════════════════

┌────────────────────────────────────────────────────────────────────────────┐
│ Orchestrator.initialize()                                                  │
│ ┌────────────────────────────────────────────────────────────────────┐   │
│ │ STEP 1: Ensure Redis session exists                               │   │
│ │ ┌────────────────────────────────────────────────────────────┐    │   │
│ │ │ session = await self.session_manager.get_session("user123")│    │   │
│ │ │    │                                                        │    │   │
│ │ │    ▼                                                        │    │   │
│ │ │ ┌──────────────────────────────────────────────────────┐   │    │   │
│ │ │ │ SessionManager.get_session(user_id="user123")        │   │    │   │
│ │ │ │ (src/services/session_manager.py)                   │   │    │   │
│ │ │ ├──────────────────────────────────────────────────────┤   │    │   │
│ │ │ │ 1. Connect to Redis (localhost:6381)                │   │    │   │
│ │ │ │    self.redis = await aioredis.from_url(...)        │   │    │   │
│ │ │ │                                                      │   │    │   │
│ │ │ │ 2. Get session from Redis:                          │   │    │   │
│ │ │ │    key = "session:user123"                          │   │    │   │
│ │ │ │    data = await self.redis.get(key)                 │   │    │   │
│ │ │ │                                                      │   │    │   │
│ │ │ │ 3. If exists: return json.loads(data)               │   │    │   │
│ │ │ │    If not: return None                              │   │    │   │
│ │ │ └──────────────────────────────────────────────────────┘   │    │   │
│ │ │                                                            │    │   │
│ │ │ if not session:                                            │    │   │
│ │ │   await self.session_manager.create_session("user123") ◄──┤    │   │
│ │ │        │                                                   │    │   │
│ │ │        ▼                                                   │    │   │
│ │ │   ┌────────────────────────────────────────────────────┐  │    │   │
│ │ │   │ SessionManager.create_session(user_id="user123")   │  │    │   │
│ │ │   ├────────────────────────────────────────────────────┤  │    │   │
│ │ │   │ 1. Create session data:                           │  │    │   │
│ │ │   │    session_data = {                               │  │    │   │
│ │ │   │      "user_id": "user123",                        │  │    │   │
│ │ │   │      "created_at": "2025-11-25T10:00:00",         │  │    │   │
│ │ │   │      "updated_at": "2025-11-25T10:00:00",         │  │    │   │
│ │ │   │      "files": []                                  │  │    │   │
│ │ │   │    }                                              │  │    │   │
│ │ │   │                                                   │  │    │   │
│ │ │   │ 2. Store in Redis:                                │  │    │   │
│ │ │   │    key = "session:user123"                        │  │    │   │
│ │ │   │    await self.redis.set(                          │  │    │   │
│ │ │   │      key,                                         │  │    │   │
│ │ │   │      json.dumps(session_data)                     │  │    │   │
│ │ │   │    )                                              │  │    │   │
│ │ │   │                                                   │  │    │   │
│ │ │   │ 3. logger.info("Created session for user123")    │  │    │   │
│ │ │   └────────────────────────────────────────────────────┘  │    │   │
│ │ └────────────────────────────────────────────────────────────┘    │   │
│ │                                                                    │   │
│ │ STEP 2-4: Register agents (TestCase, Weather, Time)               │   │
│ │ STEP 5-7: Create Router Agent                                     │   │
│ └────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
          REDIS NOW HAS:  session:user123 → {user_id, created_at, files:[]}
═══════════════════════════════════════════════════════════════════════════════

┌────────────────────────────────────────────────────────────────────────────┐
│ Orchestrator.handle_file_upload(file_content, "login.pdf", "application/pdf")│
│ (src/orchestrator/orchestrator.py)                                        │
│ ┌────────────────────────────────────────────────────────────────────┐   │
│ │ STEP 1: Parse file                                                 │   │
│ │ ┌────────────────────────────────────────────────────────────┐    │   │
│ │ │ parse_result = await self.file_parser.run_async({...})    │    │   │
│ │ │   → Returns: {"success": True, "text": "Login page..."}   │    │   │
│ │ └────────────────────────────────────────────────────────────┘    │   │
│ │                                                                     │   │
│ │ text_content = "Login page specification: User enters..."          │   │
│ │                                                                     │   │
│ │ STEP 2: Add to Redis session                                       │   │
│ │ ┌────────────────────────────────────────────────────────────┐    │   │
│ │ │ await self.session_manager.add_file_to_session(            │    │   │
│ │ │   "user123",                                               │    │   │
│ │ │   {                                                        │    │   │
│ │ │     "name": "login.pdf",                                   │    │   │
│ │ │     "type": "pdf",                                         │    │   │
│ │ │     "content": text_content,                               │    │   │
│ │ │     "size": 45678                                          │    │   │
│ │ │   }                                                        │    │   │
│ │ │ )                                                          │    │   │
│ │ │    │                                                       │    │   │
│ │ │    ▼                                                       │    │   │
│ │ │ ┌──────────────────────────────────────────────────────┐  │    │   │
│ │ │ │ SessionManager.add_file_to_session()                 │  │    │   │
│ │ │ │ (src/services/session_manager.py)                   │  │    │   │
│ │ │ ├──────────────────────────────────────────────────────┤  │    │   │
│ │ │ │ 1. Get current session from Redis:                  │  │    │   │
│ │ │ │    key = "session:user123"                          │  │    │   │
│ │ │ │    session_data = await self.get_session("user123") │  │    │   │
│ │ │ │                                                      │  │    │   │
│ │ │ │ 2. Add file info:                                   │  │    │   │
│ │ │ │    file_info["uploaded_at"] = "2025-11-25T10:05:00" │  │    │   │
│ │ │ │    session_data["files"].append(file_info)          │  │    │   │
│ │ │ │    session_data["updated_at"] = "2025-11-25T10:05:00"│ │    │   │
│ │ │ │                                                      │  │    │   │
│ │ │ │ 3. Save back to Redis:                              │  │    │   │
│ │ │ │    await self.redis.set(                            │  │    │   │
│ │ │ │      "session:user123",                             │  │    │   │
│ │ │ │      json.dumps(session_data)                       │  │    │   │
│ │ │ │    )                                                │  │    │   │
│ │ │ │                                                      │  │    │   │
│ │ │ │ 4. logger.info("Added file login.pdf to session")  │  │    │   │
│ │ │ └──────────────────────────────────────────────────────┘  │    │   │
│ │ └────────────────────────────────────────────────────────────┘    │   │
│ └────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
     REDIS UPDATED: session:user123 → {user_id, files:[{login.pdf, ...}]}
═══════════════════════════════════════════════════════════════════════════════

┌────────────────────────────────────────────────────────────────────────────┐
│ Orchestrator.handle_file_upload() - Continue                              │
│ ┌────────────────────────────────────────────────────────────────────┐   │
│ │ STEP 3: Add to FAISS for semantic search                          │   │
│ │ ┌────────────────────────────────────────────────────────────┐    │   │
│ │ │ self.faiss_service.add_document(                           │    │   │
│ │ │   text=text_content,  # "Login page specification..."     │    │   │
│ │ │   metadata={"file_name": "login.pdf", "type": "spec"}     │    │   │
│ │ │ )                                                          │    │   │
│ │ │    │                                                       │    │   │
│ │ │    ▼                                                       │    │   │
│ │ │ ┌──────────────────────────────────────────────────────┐  │    │   │
│ │ │ │ FAISSService.add_document()                          │  │    │   │
│ │ │ │ (src/services/faiss_service.py)                     │  │    │   │
│ │ │ ├──────────────────────────────────────────────────────┤  │    │   │
│ │ │ │ 1. Create embedding using OpenAI:                   │  │    │   │
│ │ │ │    response = openai.Embedding.create(              │  │    │   │
│ │ │ │      model="text-embedding-ada-002",                │  │    │   │
│ │ │ │      input=text_content                             │  │    │   │
│ │ │ │    )                                                │  │    │   │
│ │ │ │    embedding = response['data'][0]['embedding']    │  │    │   │
│ │ │ │    # embedding = [0.123, -0.456, ..., 0.234]       │  │    │   │
│ │ │ │    # (1536 dimensions)                             │  │    │   │
│ │ │ │                                                      │  │    │   │
│ │ │ │ 2. Convert to numpy array:                          │  │    │   │
│ │ │ │    vector = np.array([embedding], dtype='float32') │  │    │   │
│ │ │ │                                                      │  │    │   │
│ │ │ │ 3. Add to FAISS index:                              │  │    │   │
│ │ │ │    self.index.add(vector)                           │  │    │   │
│ │ │ │                                                      │  │    │   │
│ │ │ │ 4. Store original text and metadata:                │  │    │   │
│ │ │ │    self.documents.append(text_content)              │  │    │   │
│ │ │ │    self.metadata.append(metadata)                   │  │    │   │
│ │ │ │                                                      │  │    │   │
│ │ │ │ 5. logger.info("Added document to FAISS (total: 1)")│ │    │   │
│ │ │ └──────────────────────────────────────────────────────┘  │    │   │
│ │ └────────────────────────────────────────────────────────────┘    │   │
│ └────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
      FAISS UPDATED: user123's index has 1 document with embedding vector
═══════════════════════════════════════════════════════════════════════════════

```

---

## 🔍 Semantic Search Flow (FAISS)

```
┌────────────────────────────────────────────────────────────────────────────┐
│ User uploads SECOND file: "registration.pdf"                              │
│ Similar content to first file (both about user authentication)            │
└────────────────────────────┬───────────────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ TestCaseAgent.process({"spec": "Registration form specification..."})     │
│ (src/agents/test_case_agent.py)                                           │
│ ┌────────────────────────────────────────────────────────────────────┐   │
│ │ STEP 1: Check Redis cache                                         │   │
│ │ ┌────────────────────────────────────────────────────────────┐    │   │
│ │ │ cache_key = f"test_cases:{hash(spec_text)}"                │    │   │
│ │ │ cached = await session_manager.get_cache(cache_key)        │    │   │
│ │ │    │                                                        │    │   │
│ │ │    ▼                                                        │    │   │
│ │ │ ┌──────────────────────────────────────────────────────┐   │    │   │
│ │ │ │ SessionManager.get_cache(key)                        │   │    │   │
│ │ │ ├──────────────────────────────────────────────────────┤   │    │   │
│ │ │ │ key = "test_cases:12345678"                          │   │    │   │
│ │ │ │ data = await self.redis.get(key)                     │   │    │   │
│ │ │ │ return json.loads(data) if data else None           │   │    │   │
│ │ │ └──────────────────────────────────────────────────────┘   │    │   │
│ │ │                                                            │    │   │
│ │ │ if cached:  return cached  # Cache hit!                   │    │   │
│ │ └────────────────────────────────────────────────────────────┘    │   │
│ │                                                                     │   │
│ │ STEP 2: Check FAISS similarity (cache miss)                        │   │
│ │ ┌────────────────────────────────────────────────────────────┐    │   │
│ │ │ similar = self.faiss_service.search(                       │    │   │
│ │ │   query=spec_text,  # "Registration form spec..."         │    │   │
│ │ │   top_k=3                                                  │    │   │
│ │ │ )                                                          │    │   │
│ │ │    │                                                       │    │   │
│ │ │    ▼                                                       │    │   │
│ │ │ ┌──────────────────────────────────────────────────────┐  │    │   │
│ │ │ │ FAISSService.search(query, top_k=3)                  │  │    │   │
│ │ │ │ (src/services/faiss_service.py)                     │  │    │   │
│ │ │ ├──────────────────────────────────────────────────────┤  │    │   │
│ │ │ │ 1. Create embedding for query:                      │  │    │   │
│ │ │ │    response = openai.Embedding.create(              │  │    │   │
│ │ │ │      model="text-embedding-ada-002",                │  │    │   │
│ │ │ │      input=query                                    │  │    │   │
│ │ │ │    )                                                │  │    │   │
│ │ │ │    query_embedding = response['data'][0]['embedding']│ │    │   │
│ │ │ │                                                      │  │    │   │
│ │ │ │ 2. Convert to numpy:                                │  │    │   │
│ │ │ │    query_vector = np.array([query_embedding])      │  │    │   │
│ │ │ │                                                      │  │    │   │
│ │ │ │ 3. Search FAISS index:                              │  │    │   │
│ │ │ │    distances, indices = self.index.search(          │  │    │   │
│ │ │ │      query_vector,                                  │  │    │   │
│ │ │ │      k=top_k  # top 3                               │  │    │   │
│ │ │ │    )                                                │  │    │   │
│ │ │ │    # distances = [[0.05, 0.82, 1.23]]              │  │    │   │
│ │ │ │    # indices = [[0, 1, 2]]                          │  │    │   │
│ │ │ │                                                      │  │    │   │
│ │ │ │ 4. Calculate similarity scores:                     │  │    │   │
│ │ │ │    for i, idx in enumerate(indices[0]):            │  │    │   │
│ │ │ │      distance = distances[0][i]                     │  │    │   │
│ │ │ │      similarity = 1 / (1 + distance)                │  │    │   │
│ │ │ │      # similarity = 0.95 (very similar!)            │  │    │   │
│ │ │ │                                                      │  │    │   │
│ │ │ │ 5. Filter by threshold (0.85):                      │  │    │   │
│ │ │ │    if similarity > 0.85:                            │  │    │   │
│ │ │ │      results.append({                               │  │    │   │
│ │ │ │        "document": self.documents[idx],             │  │    │   │
│ │ │ │        "metadata": self.metadata[idx],              │  │    │   │
│ │ │ │        "similarity": 0.95                           │  │    │   │
│ │ │ │      })                                             │  │    │   │
│ │ │ │                                                      │  │    │   │
│ │ │ │ 6. Return sorted results                            │  │    │   │
│ │ │ └──────────────────────────────────────────────────────┘  │    │   │
│ │ │                                                            │    │   │
│ │ │ # Result: Found similar document (login.pdf)              │    │   │
│ │ │ # with similarity=0.95 and cached test_cases              │    │   │
│ │ │                                                            │    │   │
│ │ │ if similar and similar[0]['similarity'] > 0.95:           │    │   │
│ │ │   cached_result = similar[0]['metadata'].get('test_cases')│    │   │
│ │ │   if cached_result:                                       │    │   │
│ │ │     return cached_result  # FAISS cache hit!              │    │   │
│ │ └────────────────────────────────────────────────────────────┘    │   │
│ │                                                                     │   │
│ │ STEP 3: Generate with ADK (if no cache)                            │   │
│ │ # ... LlmAgent generates test cases ...                            │   │
│ │                                                                     │   │
│ │ STEP 4: Cache result in Redis                                      │   │
│ │ ┌────────────────────────────────────────────────────────────┐    │   │
│ │ │ await session_manager.set_cache(                           │    │   │
│ │ │   key=cache_key,                                           │    │   │
│ │ │   value=result,                                            │    │   │
│ │ │   ttl=3600  # 1 hour                                       │    │   │
│ │ │ )                                                          │    │   │
│ │ │    │                                                       │    │   │
│ │ │    ▼                                                       │    │   │
│ │ │ ┌──────────────────────────────────────────────────────┐  │    │   │
│ │ │ │ SessionManager.set_cache(key, value, ttl)            │  │    │   │
│ │ │ ├──────────────────────────────────────────────────────┤  │    │   │
│ │ │ │ await self.redis.setex(                              │  │    │   │
│ │ │ │   key="test_cases:12345678",                         │  │    │   │
│ │ │ │   time=3600,  # seconds                              │  │    │   │
│ │ │ │   value=json.dumps(value)                            │  │    │   │
│ │ │ │ )                                                    │  │    │   │
│ │ │ └──────────────────────────────────────────────────────┘  │    │   │
│ │ └────────────────────────────────────────────────────────────┘    │   │
│ │                                                                     │   │
│ │ STEP 5: Update FAISS metadata with test_cases                      │   │
│ │ (for future similarity searches)                                   │   │
│ └────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       MULTI-USER ARCHITECTURE                            │
└──────────────────────────────────────────────────────────────────────────┘

User A (user_id="alice")                     User B (user_id="bob")
     │                                             │
     ├─> GET /chat "weather in NY"                ├─> POST /upload "spec.pdf"
     │                                             │
     ▼                                             ▼
┌─────────────────────────┐               ┌─────────────────────────┐
│ Orchestrator (alice)    │               │ Orchestrator (bob)      │
├─────────────────────────┤               ├─────────────────────────┤
│ • agents: {...}         │               │ • agents: {...}         │
│ • faiss_service ─┐      │               │ • faiss_service ─┐      │
│ • session_manager├──┐   │               │ • session_manager├──┐   │
└──────────────────┼──┼───┘               └──────────────────┼──┼───┘
                   │  │                                       │  │
                   │  │                                       │  │
     ┌─────────────┘  └─────────────┐         ┌─────────────┘  └─────────┐
     │                               │         │                           │
     ▼                               │         ▼                           │
┌──────────────────┐                │    ┌──────────────────┐            │
│ FAISSService     │                │    │ FAISSService     │            │
│ (user_id=alice)  │                │    │ (user_id=bob)    │            │
├──────────────────┤                │    ├──────────────────┤            │
│ • index (1536)   │                │    │ • index (1536)   │            │
│ • documents: []  │                │    │ • documents: []  │            │
│ • metadata: []   │                │    │ • metadata: []   │            │
│                  │                │    │                  │            │
│ In-Memory        │                │    │ In-Memory        │            │
│ (per instance)   │                │    │ (per instance)   │            │
└──────────────────┘                │    └──────────────────┘            │
                                    │                                     │
                                    └──────────┬──────────────────────────┘
                                               │
                                               ▼
                                    ┌─────────────────────┐
                                    │ SessionManager      │
                                    │ (Singleton)         │
                                    ├─────────────────────┤
                                    │ • redis (shared)    │
                                    └──────────┬──────────┘
                                               │
                                               ▼
                                    ┌─────────────────────┐
                                    │   Redis Database    │
                                    │  (localhost:6381)   │
                                    ├─────────────────────┤
                                    │ session:alice → {...}│
                                    │ session:bob → {...} │
                                    │ test_cases:xxx → {...}│
                                    │ test_cases:yyy → {...}│
                                    └─────────────────────┘
```

---

## 🔑 Key Points Summary

### Redis (Global Storage):
| Key Pattern | Purpose | Lifetime | Shared? |
|-------------|---------|----------|---------|
| `session:{user_id}` | User session + files | Persistent | ❌ Per user |
| `test_cases:{hash}` | Test case cache | 1 hour TTL | ✅ All users (same spec) |
| `cache:{key}` | Generic cache | Configurable | ✅ Can be shared |

### FAISS (Per-User Storage):
| Attribute | Purpose | Lifetime | Shared? |
|-----------|---------|----------|---------|
| `index` | Vector embeddings | In-memory (lost on restart) | ❌ Per user |
| `documents` | Original text | In-memory | ❌ Per user |
| `metadata` | File info + cache | In-memory | ❌ Per user |

### Who Calls Who:

```
1. File Upload Flow:
   API → get_orchestrator() → Orchestrator.handle_file_upload()
     → SessionManager.add_file_to_session() → Redis.set("session:user123")
     → FAISSService.add_document() → OpenAI Embedding → FAISS.index.add()

2. Test Case Generation Flow:
   TestCaseAgent.process()
     → SessionManager.get_cache() → Redis.get("test_cases:xxx")
     → FAISSService.search() → OpenAI Embedding → FAISS.index.search()
     → LlmAgent generates → SessionManager.set_cache() → Redis.setex()

3. Session Management:
   Orchestrator.initialize()
     → SessionManager.get_session() → Redis.get("session:user123")
     → SessionManager.create_session() → Redis.set("session:user123")
```

---

**Generated**: 2025-11-25  
**Branch**: new_version_adk_check_routing_orchestrator
