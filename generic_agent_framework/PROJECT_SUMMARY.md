# Generic Agent Framework - Project Summary

## 📦 What's Inside

A complete, production-ready multi-agent framework built with:
- **Google ADK** (Agent Development Kit)
- **OpenAI** (via LiteLLM)
- **Redis** (session management)
- **FAISS** (optional semantic search)
- **FastAPI** (REST API)

---

## 📁 Project Structure

```
generic_agent_framework/
│
├── 📄 main.py                    # Entry point - run this!
├── 📄 requirements.txt           # Python dependencies
├── 📄 .env.example              # Environment template
├── 📄 .gitignore                # Git ignore rules
│
├── 📚 Documentation
│   ├── README.md                # Complete guide (start here!)
│   ├── QUICKSTART.md            # 5-minute setup guide
│   ├── ARCHITECTURE.md          # Deep technical overview
│   └── PROJECT_SUMMARY.md       # This file
│
├── ⚙️ config/
│   ├── __init__.py
│   └── settings.py              # Configuration management
│
└── 📦 src/
    │
    ├── 🌐 api/
    │   ├── __init__.py
    │   └── api.py               # FastAPI endpoints
    │
    ├── 🎯 orchestrator/
    │   ├── __init__.py
    │   └── orchestrator.py      # Main orchestration logic
    │
    ├── 🤖 agents/
    │   ├── __init__.py
    │   ├── base_agent.py        # Abstract base class
    │   ├── time_agent.py        # Example: Time agent
    │   └── weather_agent.py     # Example: Weather agent
    │
    └── 🔧 services/
        ├── __init__.py
        ├── session_manager.py   # Redis session management
        └── faiss_service.py     # FAISS semantic search (optional)
```

---

## 🎯 Core Components

### 1. Orchestrator (Per-User)
- Creates router agent
- Registers specialized agents
- Manages user session
- Coordinates request flow

### 2. Router Agent (LlmAgent)
- Analyzes user requests semantically
- Selects appropriate specialized agent
- No hardcoded routing rules
- Adapts to natural language

### 3. Specialized Agents
- **TimeAgent** - Provides current time
- **WeatherAgent** - Provides weather info
- **Your Agents** - Add more easily!

### 4. Session Manager
- Redis-based persistent storage
- Per-user sessions
- Cache with TTL
- Global state management

### 5. FAISS Service (Optional)
- Semantic search
- Per-user vector indexes
- OpenAI embeddings
- Similarity matching

---

## 🔄 Request Flow

```
User Request
    ↓
FastAPI Endpoint
    ↓
Get/Create Orchestrator (per user)
    ↓
Router Agent (LlmAgent) - Analyzes request
    ↓
Selects Agent (e.g., "time_agent")
    ↓
Agent Executes with Tools
    ↓
Response Returned
```

---

## ✨ Key Features

### Multi-User Support
- ✅ One orchestrator per user
- ✅ Isolated sessions
- ✅ Separate FAISS indexes
- ✅ No cross-contamination

### Intelligent Routing
- ✅ Semantic understanding (not keywords)
- ✅ Natural language processing
- ✅ Adapts to variations
- ✅ Extensible routing logic

### Easy Agent Creation
- ✅ Simple base class
- ✅ Function tools (ADK auto-converts)
- ✅ Clear templates
- ✅ Plug-and-play architecture

### Production Ready
- ✅ Logging throughout
- ✅ Error handling
- ✅ Configuration management
- ✅ Health checks
- ✅ API documentation (OpenAPI)

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Docker (for Redis)
- OpenAI API key

### Installation (5 minutes)

```bash
# 1. Setup
cd generic_agent_framework
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure
copy .env.example .env
# Edit .env with your OPENAI_API_KEY

# 3. Start Redis
docker run -d --name redis -p 6379:6379 redis:latest

# 4. Run
python main.py
```

**Server:** http://127.0.0.1:8000  
**Docs:** http://127.0.0.1:8000/docs

---

## 📖 Documentation Guide

Read in this order:

1. **QUICKSTART.md** (5 min)
   - Quick setup and testing
   - Get running immediately

2. **README.md** (15 min)
   - Complete user guide
   - How to create agents
   - API reference
   - Best practices

3. **ARCHITECTURE.md** (30 min)
   - Deep technical dive
   - Component breakdown
   - Data flow diagrams
   - Extension points

---

## 🎓 How to Add Your Agent

### 1. Create Agent File
Copy `src/agents/time_agent.py` → `src/agents/my_agent.py`

### 2. Define Tool Function
```python
def my_tool(param: str) -> str:
    """What your tool does."""
    # Your logic
    return result
```

### 3. Create ADK Agent
```python
agent = LlmAgent(
    model=LiteLlm(model=self.model),
    tools=[my_tool]  # ADK auto-converts
)
```

### 4. Register in Orchestrator
Edit `src/orchestrator/orchestrator.py`:
```python
my_agent = MyAgent(user_id, session_manager, faiss_service)
self.agents["my_agent"] = my_agent
```

### 5. Update Router Instruction
Add to router instruction:
```
- my_agent: Does XYZ tasks
```

### 6. Test
```bash
POST /chat
Headers: user-id: alice
Body: {"message": "Request for my agent"}
```

---

## 🔧 Configuration

All settings in `.env`:

```bash
# Required
OPENAI_API_KEY=sk-...
OPENAI_MODEL=openai/gpt-4o-mini

# Optional
REDIS_HOST=localhost
REDIS_PORT=6379
API_PORT=8000
```

---

## 🐛 Troubleshooting

### Redis Connection Error
```bash
docker ps | grep redis
docker run -d --name redis -p 6379:6379 redis:latest
```

### OpenAI API Error
- Check API key in `.env`
- Verify credits: https://platform.openai.com/usage

### Import Error
```bash
pip install -r requirements.txt --force-reinstall
```

### Agent Not Found
- Check agent registered in `orchestrator.py`
- Verify agent name in router instruction
- Check logs for initialization errors

---

## 📊 API Endpoints

### POST /chat
Send message to agent system

**Request:**
```json
Headers: user-id: alice
Body: {"message": "What time is it?"}
```

**Response:**
```json
{
  "response": "Current time in UTC: 09:45 PM...",
  "agent_used": "time_agent",
  "source": "orchestrator_routing"
}
```

### GET /health
System health check

**Response:**
```json
{
  "status": "healthy",
  "redis_connected": true,
  "timestamp": "2025-11-25T15:30:00Z",
  "agents_available": 2
}
```

### GET /session/{user_id}
Get user session data

**Response:**
```json
{
  "user_id": "alice",
  "files": [],
  "history": [],
  "state": {}
}
```

---

## 🎯 Design Philosophy

1. **Clean & Simple**
   - Minimal boilerplate
   - Clear separation of concerns
   - Easy to understand

2. **Extensible**
   - Add agents without modifying core
   - Clear extension points
   - Plugin architecture

3. **Production Ready**
   - Proper logging
   - Error handling
   - Configuration management
   - Health checks

4. **Developer Friendly**
   - Comprehensive docs
   - Clear examples
   - Quick start guide
   - Architecture diagrams

---

## 🚀 Next Steps

### For Development
1. Add your custom agents
2. Integrate external APIs
3. Add caching strategies
4. Extend storage options

### For Production
1. Add authentication
2. Rate limiting
3. Monitoring/metrics
4. Docker deployment
5. Load balancing

---

## 📚 Additional Resources

- **Google ADK Docs:** https://google.github.io/adk/
- **OpenAI API:** https://platform.openai.com/docs/
- **LiteLLM:** https://docs.litellm.ai/
- **Redis Python:** https://redis-py.readthedocs.io/
- **FAISS:** https://github.com/facebookresearch/faiss
- **FastAPI:** https://fastapi.tiangolo.com/

---

## 💡 Example Use Cases

1. **Multi-Agent Chatbot**
   - Time, weather, news, calculations
   - Intelligent routing to specialized agents

2. **Task Automation**
   - Email agent, calendar agent, reminder agent
   - Coordinate complex workflows

3. **Data Analysis**
   - Query agent, visualization agent, summary agent
   - Process and present data

4. **Content Generation**
   - Writer agent, editor agent, translator agent
   - Collaborative content creation

---

## ✅ Checklist for Success

- [ ] Python 3.10+ installed
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] `.env` file configured with API key
- [ ] Redis running (Docker or local)
- [ ] Server starts successfully
- [ ] Health check returns 200 OK
- [ ] Test chat request works
- [ ] Read README.md
- [ ] Understand architecture
- [ ] Ready to add agents!

---

## 🤝 Support

If you need help:
1. Check QUICKSTART.md for setup issues
2. Read ARCHITECTURE.md for technical questions
3. Review README.md for usage examples
4. Check logs for error details

---

**Ready to build your multi-agent system! 🚀**

---

*Generic Agent Framework v1.0.0*  
*Built with Google ADK + OpenAI + Redis*
