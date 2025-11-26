<!-- # New Agents - Weather & Time

## Overview
Added two simple agents to test the orchestrator's routing capabilities:

1. **WeatherAgent** - Provides weather information using Google Search
2. **TimeAgent** - Provides current time using Google Search

Both agents use **Google ADK's built-in GoogleSearchTool** (pure ADK!).

---

## Agent Details

### WeatherAgent
- **File**: `src/agents/weather_agent.py`
- **Tool**: ✅ `GoogleSearchTool()` - **ADK built-in tool**
- **How it works**: Agent uses Google Search to find current weather information
- **ADK Components**:
  - ✅ `LlmAgent` with `LiteLlm` model
  - ✅ `Runner` for execution
  - ✅ `InMemorySessionService` for session management
  - ✅ **GoogleSearchTool** (ADK built-in, no custom code needed!)
- **Example Queries**:
  - "What's the weather in New York?"
  - "Tell me the temperature in London"
  - "How's the weather in Tel Aviv?"

### TimeAgent
- **File**: `src/agents/time_agent.py`
- **Tool**: ✅ `GoogleSearchTool()` - **ADK built-in tool**
- **How it works**: Agent uses Google Search to find current time information
- **ADK Components**:
  - ✅ `LlmAgent` with `LiteLlm` model
  - ✅ `Runner` for execution
  - ✅ `InMemorySessionService` for session management
  - ✅ **GoogleSearchTool** (ADK built-in, no custom code needed!)
- **Dependencies**: None! (no pytz needed)
- **Example Queries**:
  - "What time is it in Tokyo?"
  - "What's the current time in New York?"
  - "Tell me the time in Tel Aviv"

---

## Why GoogleSearchTool?

✅ **Pure ADK**: Built-in tool from Google ADK  
✅ **No Dependencies**: No need for pytz, weather APIs, etc.  
✅ **Real Data**: Gets actual current information from Google Search  
✅ **Simple**: Just add `tools=[GoogleSearchTool()]` to LlmAgent  
✅ **Production Ready**: Google maintains and updates it

---

## Orchestrator Updates

### Router Instruction Updated
The router agent now knows about 3 agents:
```python
Available agents:
- test_case_agent: Generates test cases from specifications
- weather_agent: Provides weather information
- time_agent: Provides current time information
```

### Routing Logic
```python
Rules:
- Test cases/specifications → test_case_agent
- Weather/climate/temperature → weather_agent  
- Time/clock/timezone → time_agent
```

---

## Testing

### Manual Test (via API)
```bash
# Start server
python main_new.py

# Test weather agent
curl -X POST http://127.0.0.1:8100/chat \
  -H "Content-Type: application/json" \
  -H "user-id: test_user" \
  -d '{"message": "What'\''s the weather in New York?"}'

# Test time agent
curl -X POST http://127.0.0.1:8100/chat \
  -H "Content-Type: application/json" \
  -H "user-id: test_user" \
  -d '{"message": "What time is it in Tokyo?"}'

# Test test case agent
curl -X POST http://127.0.0.1:8100/chat \
  -H "Content-Type: application/json" \
  -H "user-id: test_user" \
  -d '{"message": "Generate test cases for login page"}'
```

### Automated Test
```bash
python test_routing.py
```

This will test all 3 agents and verify routing works correctly.

---

## Expected Flow

```
User: "What's the weather in New York?"
  ↓
Router Agent (ADK LlmAgent)
  ↓
Decision: "weather_agent"
  ↓
WeatherAgent (ADK LlmAgent + Tool)
  ↓
Tool: get_weather("New York")
  ↓
Response: "Weather in New York: Sunny, 22°C (72°F), Humidity: 45%, Wind: 10 km/h"
```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│           Orchestrator                      │
│  (One instance per user)                    │
├─────────────────────────────────────────────┤
│                                             │
│  Router Agent (✅ ADK LlmAgent)             │
│    ↓                                        │
│    Decides which agent to use               │
│    ↓                                        │
│  ┌─────────────────────────────────────┐   │
│  │ test_case_agent (✅ ADK)            │   │
│  │  - Generates test cases             │   │
│  │  - Uses ADK Runner                  │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │ weather_agent (✅ ADK)              │   │
│  │  - Tool: get_weather()              │   │
│  │  - Uses ADK Runner                  │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │ time_agent (✅ ADK)                 │   │
│  │  - Tool: get_current_time()         │   │
│  │  - Uses ADK Runner                  │   │
│  └─────────────────────────────────────┘   │
│                                             │
└─────────────────────────────────────────────┘
```

---

## Key Benefits

1. ✅ **Pure ADK**: All agents use Google ADK (LlmAgent, Runner, tools)
2. ✅ **Intelligent Routing**: Router agent decides automatically
3. ✅ **Extensible**: Easy to add more agents
4. ✅ **Tool Integration**: ADK automatically converts functions to tools
5. ✅ **Multi-user**: Each user gets isolated orchestrator instance

---

**Created**: 2025-11-25
**Branch**: new_version_adk_check_routing_orchestrator -->
