# Test Case Agent (Google ADK + OpenAI via LiteLLM)

Generates structured test cases (JSON) from a specification using OpenAI models while leveraging Google ADK for agent abstraction and (optionally) orchestration. Current focus: test case generation through ADK `LlmAgent` and a lightweight orchestrator that prefers ADK's `Runner` when available.

## Features
- FastAPI API (`/run`, `/upload`, `/docs`)
- PDF or JSON spec ingestion
- Google ADK agent class (`TestCaseAgent`) using OpenAI model via LiteLLM naming (`openai/gpt-4o-mini` default)
- Fallback manual loop if ADK Runner construction fails
- Ready for future RAG (Redis + FAISS) integration

## Environment Variables
Set before running the server (PowerShell example):
```powershell
$env:OPENAI_API_KEY = "<your-key>"
$env:OPENAI_MODEL = "openai/gpt-4o-mini"  # optional override
```

## Installation
```powershell
python -m venv venv
./venv/Scripts/Activate.ps1
pip install -r requirements.txt
```

## Run the API
```powershell
python -m uvicorn src.api:app --host 127.0.0.1 --port 8100
```
Visit: http://127.0.0.1:8100/docs

## Endpoints
| Method | Path    | Description |
|--------|---------|-------------|
| POST   | /run    | Pass a JSON body like `{ "spec": "Text spec..." }` and receive generated test cases. |
| POST   | /upload | Upload a `.pdf` or `.json` file containing the specification. |
| GET    | /       | Basic health/welcome message. |

## Response Format (example)
```json
{
	"results": [
		{
			"agent": "Agent1",
			"response": {
				"test_cases": [
					{
						"id": "TC-001",
						"title": "Login with valid credentials",
						"steps": ["Navigate to login page", "Enter valid credentials", "Submit"],
						"expected_result": "User is authenticated and redirected",
						"tags": ["login", "functional"],
						"priority": "high"
					}
				]
			}
		}
	]
}
```

## ADK Integration
- `TestCaseAgent` subclasses `LlmAgent` and delegates execution to ADK.
- `TestCaseOrchestrator` attempts to build a `Runner` from ADK; if not available or fails, it iterates agents manually.
- Model name uses LiteLLM-style prefix: `openai/<model>`; ensure your ADK build supports LiteLLM integration.

## Extending
1. Add RAG: integrate FAISS index build and retrieval before agent call.
2. Add caching: use Redis to store spec → test cases mapping.
3. Add output schema validation: enforce JSON schema pre/post generation.
4. Add multiple specialized agents (e.g., security, performance) and let Runner coordinate.

## Development Notes
- Avoid committing secrets (.env ignored).
- Branch for improvements: `upgrade_adk_test_cases`.
- Keep responses strictly JSON to simplify client parsing.

## License
Internal/POC – add appropriate license if distributing.