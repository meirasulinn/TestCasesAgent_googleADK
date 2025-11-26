"""
Main entry point for the Generic Agent Framework.
Starts the FastAPI server with uvicorn.
"""
import uvicorn
from config.settings import settings

if __name__ == "__main__":
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║        Generic Agent Framework with Google ADK            ║
║                   Version: 1.0.0                          ║
╚═══════════════════════════════════════════════════════════╝

Starting server on http://{settings.API_HOST}:{settings.API_PORT}

Features:
  ✓ Multi-user orchestration
  ✓ Intelligent agent routing
  ✓ Google ADK agents
  ✓ OpenAI via LiteLLM ({settings.OPENAI_MODEL})
  ✓ Redis session management
  ✓ FAISS semantic search (optional)

Available Agents:
  • TimeAgent - Current time for timezones
  • WeatherAgent - Weather information

API Documentation: http://{settings.API_HOST}:{settings.API_PORT}/docs

Press Ctrl+C to stop
""")
    
    uvicorn.run(
        "src.api.api:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
        log_level="info"
    )
