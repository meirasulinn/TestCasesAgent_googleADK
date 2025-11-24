"""
Main entry point for the Multi-Agent Test Case Generator.
"""
import uvicorn
from src.config.settings import settings

if __name__ == "__main__":
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║   Multi-Agent Test Case Generator (Google ADK)            ║
║   Version: 2.0                                            ║
╚═══════════════════════════════════════════════════════════╝

Starting server on http://{settings.API_HOST}:{settings.API_PORT}

Features:
  ✓ Multi-user orchestration
  ✓ Google ADK agents
  ✓ OpenAI via LiteLLM ({settings.OPENAI_MODEL})
  ✓ Redis session management
  ✓ FAISS session-local search

Press Ctrl+C to stop
""")
    
    uvicorn.run(
        "src.api.api:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
        log_level="info"
    )
