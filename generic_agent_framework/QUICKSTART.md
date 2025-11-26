# Quick Start Guide - Generic Agent Framework

Get up and running in 5 minutes! ⚡

## Step 1: Setup Environment (2 minutes)

```bash
# Navigate to project
cd generic_agent_framework

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configure (1 minute)

```bash
# Copy environment template
copy .env.example .env   # Windows
# cp .env.example .env   # Linux/Mac

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=sk-your-key-here
```

## Step 3: Start Redis (1 minute)

```bash
# Using Docker (easiest):
docker run -d --name redis -p 6379:6379 redis:latest

# Or if you have Redis installed locally, just start it
# redis-server
```

## Step 4: Run Server (30 seconds)

```bash
python main.py
```

Server starts at: **http://127.0.0.1:8000**

## Step 5: Test (30 seconds)

Open browser: **http://127.0.0.1:8000/docs**

### Try These Examples:

**1. Time Query:**
```http
POST /chat
Headers: user-id: alice
Body: {
  "message": "What time is it in New York?"
}
```

**2. Weather Query:**
```http
POST /chat
Headers: user-id: alice
Body: {
  "message": "What's the weather in London?"
}
```

**3. Health Check:**
```http
GET /health
```

---

## What Just Happened?

1. **Router Agent** analyzed your message
2. **Selected appropriate agent** (TimeAgent or WeatherAgent)
3. **Agent executed** with its function tool
4. **Response returned** to you

---

## Next Steps

### Add Your Own Agent:

1. Copy `src/agents/time_agent.py` → `src/agents/my_agent.py`
2. Modify the tool function
3. Register in `src/orchestrator/orchestrator.py`
4. Update router instruction
5. Restart server

See **README.md** for detailed instructions!

---

## Troubleshooting

**Redis Connection Error?**
```bash
# Check if Redis is running:
docker ps | grep redis

# If not running, start it:
docker run -d --name redis -p 6379:6379 redis:latest
```

**OpenAI API Error?**
- Check your API key in `.env`
- Verify you have credits: https://platform.openai.com/usage

**Import Error?**
```bash
# Reinstall dependencies:
pip install -r requirements.txt --force-reinstall
```

---

**Ready to build your agents! 🚀**
