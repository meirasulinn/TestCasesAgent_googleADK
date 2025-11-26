# Generic Agent Framework with Google ADK

🎯 **Production-ready multi-agent framework with intelligent routing**

A clean, extensible framework for building multi-agent systems using Google ADK (Agent Development Kit) with OpenAI integration, Redis session management, and FAISS semantic search.

---

## 🌟 Features

✅ **Intelligent Routing** - Router agent automatically selects the right agent for each request  
✅ **Multi-User Support** - Isolated sessions and data for each user  
✅ **Google ADK Integration** - Leverages Google's Agent Development Kit  
✅ **OpenAI Compatible** - Works with OpenAI models via LiteLLM  
✅ **Redis Sessions** - Persistent state and caching  
✅ **FAISS Search** - Per-user semantic search (optional)  
✅ **Easy Agent Creation** - Simple template for adding new agents  
✅ **Production Ready** - Clean architecture, logging, error handling  

---

## 📋 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    USER REQUEST                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │      ORCHESTRATOR            │
        │  (One per user)              │
        └──────────────┬───────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │      ROUTER AGENT            │
        │  (LlmAgent - decides route)  │
        └──────────────┬───────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────────┐
        │   Selected Agent (TimeAgent, etc.)       │
        │   └─> Execute with tools                 │
        └──────────────┬───────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │         RESPONSE              │
        └──────────────────────────────┘
```

### Storage Architecture

- **Redis**: Global session storage (user data, files, cache)
- **FAISS**: Per-user semantic search (in-memory, optional)
- **ADK Sessions**: Ephemeral conversation context (per-agent)

---

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.10+
- Docker (for Redis)
- OpenAI API key

### 2. Installation

```bash
# Clone or copy this framework
cd generic_agent_framework

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

```bash
# Copy example environment file
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/Mac

# Edit .env with your settings:
# - Add your OPENAI_API_KEY
# - Configure Redis connection (default: localhost:6379)
# - Adjust other settings as needed
```

### 4. Start Redis

```bash
# Using Docker (recommended)
docker run -d --name redis -p 6379:6379 redis:latest

# Or use existing Redis instance
# Just update REDIS_HOST and REDIS_PORT in .env
```

### 5. Run the Server

```bash
python main.py
```

Server starts at: **http://127.0.0.1:8000**

### 6. Test the API

Open your browser: **http://127.0.0.1:8000/docs**

Try these examples:
```json
// Chat endpoint
POST /chat
Headers: user-id: alice
Body: {"message": "What time is it in New York?"}

// Health check
GET /health
```

---

## 🔧 Creating Your Own Agent

### Step 1: Create Agent File

Create `src/agents/your_agent.py`:

```python
"""
YourAgent - Description of what your agent does.
"""
import logging
from typing import Dict, Any
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types
from src.agents.base_agent import BaseAgent
from config.settings import settings

logger = logging.getLogger(__name__)


class YourAgent(BaseAgent):
    """Agent that does XYZ."""
    
    def __init__(self, user_id: str, session_manager, faiss_service=None):
        """Initialize YourAgent."""
        self.model = settings.OPENAI_MODEL
        
        super().__init__(
            name="YourAgent",
            user_id=user_id,
            session_manager=session_manager,
            faiss_service=faiss_service
        )
        
        # Create ADK agent with function tool
        self.adk_agent = self.create_adk_agent()
        
        # ADK services
        self.adk_session_service = InMemorySessionService()
        self.adk_artifact_service = InMemoryArtifactService()
        
        logger.info(f"YourAgent created for user {user_id}")
    
    def create_adk_agent(self) -> LlmAgent:
        """Create Google ADK LlmAgent with tools."""
        
        # Define your tool function
        def your_tool_function(param: str) -> str:
            """
            Description of what this tool does.
            
            Args:
                param: Description of parameter
                
            Returns:
                Result string
            """
            # Your logic here
            return f"Result: {param}"
        
        instruction = """You are a helpful assistant that does XYZ.

Your task: [Describe what this agent should do]

Steps:
1. Understand user request
2. Use your_tool_function if needed
3. Provide helpful response
"""
        
        # Create LlmAgent with function tool
        agent = LlmAgent(
            model=LiteLlm(model=self.model),
            name=self.name,
            instruction=instruction,
            tools=[your_tool_function]  # ADK auto-converts to tool
        )
        
        return agent
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process user request."""
        message = input_data.get("message", "")
        
        logger.info(f"{self.name} processing: {message[:100]}...")
        
        # Create ADK session for this request
        adk_session = await self.adk_session_service.create_session(
            app_name=f"{self.name.lower()}_{self.user_id}",
            user_id=self.user_id
        )
        
        # Create Runner
        runner = Runner(
            app_name=f"{self.name.lower()}_{self.user_id}",
            agent=self.adk_agent,
            session_service=self.adk_session_service,
            artifact_service=self.adk_artifact_service
        )
        
        # Prepare user message
        user_content = types.Content(
            role='user',
            parts=[types.Part(text=message)]
        )
        
        # Run agent and collect response
        response_text = ""
        async for event in runner.run_async(
            user_id=self.user_id,
            session_id=adk_session.id,
            new_message=user_content
        ):
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text'):
                        response_text += part.text
        
        return {
            "response": response_text.strip(),
            "source": self.name
        }
```

### Step 2: Register Agent in Orchestrator

Edit `src/orchestrator/orchestrator.py`:

```python
# Add import at top
from src.agents.your_agent import YourAgent

# In initialize() method, add:
your_agent = YourAgent(
    user_id=self.user_id,
    session_manager=self.session_manager,
    faiss_service=self.faiss_service  # optional
)
self.agents["your_agent"] = your_agent
```

### Step 3: Update Router Instruction

In `orchestrator.py`, update router instruction:

```python
instruction=f"""You are an intelligent router for a multi-agent system.

Available agents:
- time_agent: Provides current time for different timezones
- weather_agent: Provides weather information for cities
- your_agent: Does XYZ tasks  ← ADD THIS

Your job:
1. Analyze the user's request
2. Determine which agent should handle it
3. Respond ONLY with the agent name

Rules:
- If request is about time → "time_agent"
- If request is about weather → "weather_agent"
- If request is about XYZ → "your_agent"  ← ADD THIS
- Respond with ONLY the agent name, nothing else"""
```

### Step 4: Test Your Agent

```bash
# Restart server
python main.py

# Test via API
POST http://127.0.0.1:8000/chat
Headers: user-id: alice
Body: {"message": "Request that triggers your agent"}
```

---

## 📁 Project Structure

```
generic_agent_framework/
├── main.py                    # Entry point
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
├── README.md                 # This file
│
├── config/
│   ├── __init__.py
│   └── settings.py           # Configuration management
│
├── src/
│   ├── __init__.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── api.py            # FastAPI endpoints
│   │
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   └── orchestrator.py   # Main orchestration logic
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py     # Base class for all agents
│   │   ├── time_agent.py     # Example: Time agent
│   │   └── weather_agent.py  # Example: Weather agent
│   │
│   └── services/
│       ├── __init__.py
│       ├── session_manager.py # Redis session management
│       └── faiss_service.py   # FAISS semantic search (optional)
```

---

## 🔌 API Endpoints

### POST /chat
Send chat message to the system. Router automatically selects appropriate agent.

**Request:**
```json
Headers: user-id: alice
Body: {
  "message": "What time is it in London?"
}
```

**Response:**
```json
{
  "response": "Current time in London: 03:15 PM on Monday, November 25, 2025 (UTC+0)",
  "agent_used": "time_agent"
}
```

### GET /health
Check system health and connection status.

**Response:**
```json
{
  "status": "healthy",
  "redis_connected": true,
  "timestamp": "2025-11-25T15:30:00Z"
}
```

### GET /session/{user_id}
Get user session data (files, history).

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

## ⚙️ Configuration Options

Edit `.env` file:

```bash
# OpenAI Configuration (REQUIRED)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=openai/gpt-4o-mini

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Session Management
SESSION_TTL=3600  # 1 hour in seconds

# FAISS Configuration (if using semantic search)
FAISS_DIMENSION=1536
FAISS_SIMILARITY_THRESHOLD=0.85

# API Configuration
API_HOST=127.0.0.1
API_PORT=8000

# Google ADK
ADK_APP_NAME=generic_agent_framework
```

---

## 🎓 How It Works

### 1. Request Flow

```
User → API Endpoint → Orchestrator → Router Agent → Selected Agent → Response
```

### 2. Router Agent

The router is an `LlmAgent` that:
- Analyzes user requests
- Decides which specialized agent should handle it
- Returns agent name (e.g., "time_agent")

### 3. Agent Execution

Each agent:
- Has its own ADK session
- Can use function tools (ADK auto-converts)
- Returns structured response

### 4. Multi-User Isolation

- Each user gets separate `Orchestrator` instance
- Redis sessions keyed by `session:{user_id}`
- FAISS instances isolated per user

---

## 🛠️ Advanced Features

### Using FAISS for Semantic Search

```python
# In your agent's process() method:
similar_docs = await self.faiss_service.search(
    query=user_message,
    top_k=3
)

for doc in similar_docs:
    print(f"Similar: {doc['document'][:100]}...")
```

### Caching with Redis

```python
# Cache result
await self.session_manager.set_cache(
    key="my_cache_key",
    value={"result": "data"},
    ttl=3600  # 1 hour
)

# Get cached result
cached = await self.session_manager.get_cache("my_cache_key")
```

### Adding Custom Tools

```python
def custom_tool(param1: str, param2: int) -> dict:
    """
    Your custom tool logic.
    ADK will automatically convert this to a tool.
    """
    return {
        "result": f"Processed {param1} with {param2}"
    }

# Add to LlmAgent
agent = LlmAgent(
    model=LiteLlm(model=self.model),
    tools=[custom_tool]
)
```

---

## 🐛 Troubleshooting

### Redis Connection Error
```bash
# Check if Redis is running
docker ps | grep redis

# Start Redis
docker run -d --name redis -p 6379:6379 redis:latest
```

### OpenAI API Error
```bash
# Verify API key in .env
echo $OPENAI_API_KEY

# Test API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Agent Not Found
- Check agent is registered in `orchestrator.py`
- Verify agent name matches router instruction
- Check logs for agent initialization

### Import Errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

---

## 📚 Resources

- [Google ADK Documentation](https://google.github.io/adk/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [LiteLLM Documentation](https://docs.litellm.ai/)
- [Redis Python Client](https://redis-py.readthedocs.io/)
- [FAISS Documentation](https://github.com/facebookresearch/faiss)

---

## 📝 Best Practices

1. **One agent per responsibility** - Keep agents focused
2. **Use function tools** - Let ADK auto-convert Python functions
3. **Cache expensive operations** - Use Redis caching
4. **Log everything** - Use Python logging module
5. **Handle errors gracefully** - Try/except with meaningful messages
6. **Test incrementally** - Test each agent independently first
7. **Keep instructions clear** - Router needs clear agent descriptions

---

## 🚢 Deployment

### Docker Deployment

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

### Environment Variables

Set these in production:
- `OPENAI_API_KEY` (required)
- `REDIS_HOST` (point to Redis instance)
- `API_PORT` (change from 8000 if needed)

---

## 📄 License

MIT License - Feel free to use in your projects!

---

## 🤝 Contributing

This is a generic framework - customize it for your needs:
1. Add new agents in `src/agents/`
2. Register in `orchestrator.py`
3. Update router instruction
4. Test and iterate!

---

**Created with ❤️ using Google ADK + OpenAI**
