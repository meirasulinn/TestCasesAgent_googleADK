"""
FastAPI application with pure ADK orchestration (AsyncRunner + Tools).
"""
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from typing import List
import io
import asyncio
import logging
from PyPDF2 import PdfReader
from src.agents.adk_orchestrator import ADKTestCaseOrchestrator
from src.agents.google_adk_agent import TestCaseAgent
import json
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ADK Test Case Agent", version="2.0")

# Initialize ADK orchestrator
orchestrator = ADKTestCaseOrchestrator()
agent1 = TestCaseAgent("Agent1")
agent2 = TestCaseAgent("Agent2")
orchestrator.register_agent(agent1)
orchestrator.register_agent(agent2)

logger.info("ADK Test Case Agent API initialized")


@app.get("/")
def read_root():
    """Health check endpoint."""
    return {
        "message": "Welcome to ADK Test Case Agent API (v2.0 - Pure ADK Orchestration)",
        "version": "2.0",
        "features": [
            "ADK AsyncRunner orchestration",
            "ADK Tools for RAG",
            "Redis + FAISS caching",
            "OpenAI gpt-4o-mini"
        ]
    }


@app.post("/run")
async def run_agents(input_data: dict):
    """
    Generate test cases from specification.
    
    Input: {"spec": "Specification text"}
    Output: {"rag_source": "cache|generated|faiss_cache", "results": [...]}
    """
    print(f"\n[API /run] Received POST request with data keys: {list(input_data.keys())}")
    
    try:
        results = await orchestrator.run(input_data)
        print(f"[API /run] Returning results\n")
        return {"results": results}
    except Exception as e:
        logger.error(f"Error in /run: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload PDF or JSON specification file.
    
    PDF: Extracts text and generates test cases
    JSON: Parses directly and generates test cases
    """
    filename = (file.filename or "").lower()
    raw_bytes = file.file.read()
    
    print(f"[API /upload] Received file: {filename}")
    
    # Try PDF first
    if filename.endswith(".pdf") or file.content_type == "application/pdf":
        try:
            pdf_stream = io.BytesIO(raw_bytes)
            reader = PdfReader(pdf_stream)
            extracted_text: List[str] = []
            for page in reader.pages:
                try:
                    extracted_text.append(page.extract_text() or "")
                except Exception:
                    extracted_text.append("")
            spec_text = "\n".join(t for t in extracted_text if t.strip())
            if not spec_text.strip():
                return JSONResponse(status_code=422, content={"error": "Failed to extract text from PDF"})
            
            input_data = {"spec": spec_text}
            results = await orchestrator.run(input_data)
            return {"source": "pdf", "results": results}
        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            return JSONResponse(status_code=400, content={"error": f"PDF processing failed: {e}"})
    
    # Fallback: assume JSON
    try:
        text = raw_bytes.decode("utf-8")
        if filename.endswith(".json") or file.content_type == "application/json":
            input_data = json.loads(text)
        else:
            input_data = {"spec": text}
        
        results = await orchestrator.run(input_data)
        return {"source": "json", "results": results}
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        return JSONResponse(status_code=400, content={"error": f"Invalid JSON: {e}"})
    except Exception as e:
        logger.error(f"File processing error: {e}")
        return JSONResponse(status_code=400, content={"error": str(e)})


@app.post("/health")
async def health_check():
    """ADK health check with runner status."""
    return {
        "status": "healthy",
        "orchestrator": "ADK AsyncRunner",
        "agents": [agent.name for agent in orchestrator.agents],
        "features": ["RAG Tools", "Redis Cache", "FAISS Search"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8100)
