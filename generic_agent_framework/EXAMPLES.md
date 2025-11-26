# Examples - Generic Agent Framework

Common usage patterns and examples for the Generic Agent Framework.

---

## 📋 Table of Contents

1. [Basic Chat Examples](#basic-chat-examples)
2. [Multi-User Examples](#multi-user-examples)
3. [Creating Custom Agent](#creating-custom-agent)
4. [Using Redis Cache](#using-redis-cache)
5. [Using FAISS Search](#using-faiss-search)
6. [Error Handling](#error-handling)

---

## 1. Basic Chat Examples

### Example 1: Ask for Time

**Request:**
```bash
curl -X POST "http://127.0.0.1:8000/chat" \
  -H "Content-Type: application/json" \
  -H "user-id: alice" \
  -d '{"message": "What time is it in New York?"}'
```

**Response:**
```json
{
  "response": "Current time in New York: 09:45 AM on Monday, November 25, 2025 (UTC-5)",
  "agent_used": "time_agent",
  "source": "orchestrator_routing"
}
```

**What Happened:**
1. Router analyzed "time" + "New York"
2. Selected `time_agent`
3. TimeAgent called `get_current_time("New York")`
4. Returned formatted time

---

### Example 2: Ask for Weather

**Request:**
```bash
curl -X POST "http://127.0.0.1:8000/chat" \
  -H "Content-Type: application/json" \
  -H "user-id: bob" \
  -d '{"message": "What is the weather in London?"}'
```

**Response:**
```json
{
  "response": "Weather in London: Cloudy, 15°C, Humidity: 70%",
  "agent_used": "weather_agent",
  "source": "orchestrator_routing"
}
```

**What Happened:**
1. Router analyzed "weather" + "London"
2. Selected `weather_agent`
3. WeatherAgent called `get_weather("London")`
4. Returned mock weather data

---

### Example 3: Natural Language Variations

Router understands variations:

**All route to time_agent:**
```json
{"message": "What time is it in Israel?"}
{"message": "Tell me the current time in Tel Aviv"}
{"message": "What's the clock showing in Jerusalem?"}
{"message": "Time in Israel please"}
```

**All route to weather_agent:**
```json
{"message": "How's the weather in Paris?"}
{"message": "Is it raining in Tokyo?"}
{"message": "What's the temperature in New York?"}
{"message": "Climate in London"}
```

---

## 2. Multi-User Examples

### Users Are Isolated

**Alice's Request:**
```bash
curl -X POST "http://127.0.0.1:8000/chat" \
  -H "user-id: alice" \
  -d '{"message": "What time is it?"}'
```

**Bob's Request:**
```bash
curl -X POST "http://127.0.0.1:8000/chat" \
  -H "user-id: bob" \
  -d '{"message": "What time is it?"}'
```

**Result:**
- Alice gets separate orchestrator
- Bob gets separate orchestrator
- No cross-contamination
- Sessions isolated in Redis

---

### Get User Session

**Request:**
```bash
curl -X GET "http://127.0.0.1:8000/session/alice"
```

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

## 3. Creating Custom Agent

### Example: Calculator Agent

**Step 1: Create `src/agents/calculator_agent.py`**

```python
"""
CalculatorAgent - Performs mathematical calculations.
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


class CalculatorAgent(BaseAgent):
    """Agent that performs calculations."""
    
    def __init__(self, user_id: str, session_manager, faiss_service=None):
        """Initialize CalculatorAgent."""
        self.model = settings.OPENAI_MODEL
        
        super().__init__(
            name="CalculatorAgent",
            user_id=user_id,
            session_manager=session_manager,
            faiss_service=faiss_service
        )
        
        self.adk_agent = self.create_adk_agent()
        self.adk_session_service = InMemorySessionService()
        self.adk_artifact_service = InMemoryArtifactService()
        
        logger.info(f"CalculatorAgent created for user {user_id}")
    
    def create_adk_agent(self) -> LlmAgent:
        """Create ADK agent with calculator tool."""
        
        def calculate(expression: str) -> str:
            """
            Safely evaluate mathematical expression.
            
            Args:
                expression: Math expression (e.g., "2 + 2", "10 * 5")
                
            Returns:
                Calculation result
            """
            try:
                # Safe evaluation (only math operations)
                allowed_chars = set("0123456789+-*/(). ")
                if not all(c in allowed_chars for c in expression):
                    return "Error: Invalid characters in expression"
                
                result = eval(expression)
                return f"{expression} = {result}"
            except Exception as e:
                return f"Error calculating: {str(e)}"
        
        instruction = """You are a helpful calculator assistant.

Your task: Help users with mathematical calculations.

When a user asks for calculation:
1. Extract the mathematical expression
2. Use the calculate function
3. Present the result clearly

Examples:
- "What is 2 + 2?" → Use calculate("2 + 2")
- "Calculate 100 divided by 5" → Use calculate("100 / 5")

Be helpful and accurate.
"""
        
        agent = LlmAgent(
            model=LiteLlm(model=self.model),
            name=self.name,
            instruction=instruction,
            tools=[calculate]
        )
        
        return agent
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process calculation request."""
        message = input_data.get("message", "")
        
        logger.info(f"CalculatorAgent processing: {message[:100]}...")
        
        adk_session = await self.adk_session_service.create_session(
            app_name=f"calculator_agent_{self.user_id}",
            user_id=self.user_id
        )
        
        runner = Runner(
            app_name=f"calculator_agent_{self.user_id}",
            agent=self.adk_agent,
            session_service=self.adk_session_service,
            artifact_service=self.adk_artifact_service
        )
        
        user_content = types.Content(
            role='user',
            parts=[types.Part(text=message)]
        )
        
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
            "source": "calculator_agent"
        }
```

**Step 2: Register in `src/orchestrator/orchestrator.py`**

```python
# Add import
from src.agents.calculator_agent import CalculatorAgent

# In initialize() method:
calculator_agent = CalculatorAgent(
    user_id=self.user_id,
    session_manager=self.session_manager,
    faiss_service=self.faiss_service
)
self.agents["calculator_agent"] = calculator_agent

# Update router instruction:
router_instruction = f"""You are an intelligent router for a multi-agent system.

Available agents:
- time_agent: Provides current time for different timezones
- weather_agent: Provides weather information for cities
- calculator_agent: Performs mathematical calculations  ← ADD THIS

Your job:
1. Analyze the user's request
2. Determine which agent should handle it
3. Respond ONLY with the agent name

Rules:
- If about time → "time_agent"
- If about weather → "weather_agent"
- If about calculations, math → "calculator_agent"  ← ADD THIS
- Respond with ONLY the agent name
"""
```

**Step 3: Test**

```bash
curl -X POST "http://127.0.0.1:8000/chat" \
  -H "Content-Type: application/json" \
  -H "user-id: alice" \
  -d '{"message": "What is 25 * 4?"}'
```

**Response:**
```json
{
  "response": "25 * 4 = 100",
  "agent_used": "calculator_agent",
  "source": "orchestrator_routing"
}
```

---

## 4. Using Redis Cache

### Example: Cache Expensive Operation

**In your agent's `process()` method:**

```python
async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    message = input_data.get("message", "")
    
    # Create cache key
    import hashlib
    cache_key = f"result:{hashlib.md5(message.encode()).hexdigest()}"
    
    # Check cache
    cached_result = await self.session_manager.get_cache(cache_key)
    if cached_result:
        logger.info(f"Cache hit for key {cache_key}")
        return {
            "response": cached_result["response"],
            "source": "cache",
            "agent_used": self.name
        }
    
    # Generate result (expensive operation)
    result = await self._expensive_operation(message)
    
    # Cache result for 1 hour
    await self.session_manager.set_cache(
        cache_key,
        {"response": result},
        ttl=3600
    )
    
    return {
        "response": result,
        "source": "fresh",
        "agent_used": self.name
    }
```

---

## 5. Using FAISS Search

### Example: Find Similar Documents

**Add documents to FAISS:**

```python
# In your agent or orchestrator
await self.faiss_service.add_document(
    text="User manual for login feature: Users can login with email and password...",
    metadata={
        "doc_type": "manual",
        "topic": "authentication",
        "timestamp": "2025-11-25T10:00:00Z"
    }
)

await self.faiss_service.add_document(
    text="Registration process specification: New users create account...",
    metadata={
        "doc_type": "spec",
        "topic": "registration",
        "timestamp": "2025-11-25T10:05:00Z"
    }
)
```

**Search for similar documents:**

```python
# In your agent's process() method
query = "How do users sign in?"

similar_docs = await self.faiss_service.search(query, top_k=3)

for doc in similar_docs:
    print(f"Similarity: {doc['similarity']:.2f}")
    print(f"Document: {doc['document'][:100]}...")
    print(f"Metadata: {doc['metadata']}")
```

**Output:**
```
Similarity: 0.92
Document: User manual for login feature: Users can login with email and password...
Metadata: {'doc_type': 'manual', 'topic': 'authentication', ...}

Similarity: 0.78
Document: Registration process specification: New users create account...
Metadata: {'doc_type': 'spec', 'topic': 'registration', ...}
```

---

## 6. Error Handling

### Example: Handle Agent Errors

**In orchestrator:**

```python
async def handle_chat(self, message: str) -> Dict[str, Any]:
    try:
        agent_name = await self._route_to_agent(message)
        agent = self.agents.get(agent_name)
        
        if not agent:
            return {
                "response": "Sorry, I couldn't find an appropriate agent for your request.",
                "error": "agent_not_found",
                "agent_used": "none"
            }
        
        result = await agent.process({"message": message})
        return result
        
    except Exception as e:
        logger.error(f"Error handling chat: {e}", exc_info=True)
        return {
            "response": "Sorry, an error occurred processing your request.",
            "error": str(e),
            "agent_used": "error"
        }
```

**Example Error Response:**

```bash
curl -X POST "http://127.0.0.1:8000/chat" \
  -H "user-id: alice" \
  -d '{"message": "test"}'
```

```json
{
  "response": "Sorry, an error occurred processing your request.",
  "error": "OpenAI API rate limit exceeded",
  "agent_used": "error"
}
```

---

## 7. Health Check

**Request:**
```bash
curl -X GET "http://127.0.0.1:8000/health"
```

**Healthy Response:**
```json
{
  "status": "healthy",
  "redis_connected": true,
  "timestamp": "2025-11-25T15:30:00Z",
  "agents_available": 2
}
```

**Unhealthy Response:**
```json
{
  "status": "degraded",
  "redis_connected": false,
  "timestamp": "2025-11-25T15:30:00Z",
  "agents_available": 2
}
```

---

## 8. Python Client Example

**Create a simple Python client:**

```python
import requests

class AgentClient:
    def __init__(self, base_url="http://127.0.0.1:8000", user_id="alice"):
        self.base_url = base_url
        self.user_id = user_id
    
    def chat(self, message: str):
        """Send chat message."""
        response = requests.post(
            f"{self.base_url}/chat",
            headers={"user-id": self.user_id},
            json={"message": message}
        )
        return response.json()
    
    def health(self):
        """Check health."""
        response = requests.get(f"{self.base_url}/health")
        return response.json()
    
    def get_session(self):
        """Get session data."""
        response = requests.get(f"{self.base_url}/session/{self.user_id}")
        return response.json()


# Usage
client = AgentClient(user_id="alice")

# Ask for time
result = client.chat("What time is it in Tokyo?")
print(result["response"])

# Ask for weather
result = client.chat("What's the weather in Paris?")
print(result["response"])

# Check health
health = client.health()
print(f"Status: {health['status']}")
```

---

**More examples coming soon! 🚀**
