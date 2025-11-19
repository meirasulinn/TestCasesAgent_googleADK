from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from typing import List
import io
from PyPDF2 import PdfReader
from src.agents.test_case_orchestrator import TestCaseOrchestrator
from src.agents.google_adk_agent import TestCaseAgent
import json

app = FastAPI()

# Initialize orchestrator
orchestrator = TestCaseOrchestrator()
agent1 = TestCaseAgent("Agent1")
agent2 = TestCaseAgent("Agent2")
orchestrator.register_agent(agent1)
orchestrator.register_agent(agent2)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Test Case Agent API!"}

@app.post("/run")
def run_agents(input_data: dict):
    results = orchestrator.run(input_data)
    return {"results": results}

@app.post("/upload")
def upload_file(file: UploadFile = File(...)):
    """Upload a JSON or PDF specification file and generate test cases.

    JSON: Parsed directly as dict.
    PDF: Extracts concatenated text from all pages and sends as {'spec': <text>}.
    """
    filename = (file.filename or "").lower()
    raw_bytes = file.file.read()
    # Try PDF first if extension or content type matches
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
            results = orchestrator.run(input_data)
            return {"source": "pdf", "results": results}
        except Exception as e:
            return JSONResponse(status_code=400, content={"error": f"PDF processing failed: {e}"})
    # Fallback: assume JSON text
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return JSONResponse(status_code=400, content={"error": "Unsupported file encoding (expected UTF-8 or PDF)"})
    try:
        input_data = json.loads(text)
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON file"})
    results = orchestrator.run(input_data)
    return {"source": "json", "results": results}