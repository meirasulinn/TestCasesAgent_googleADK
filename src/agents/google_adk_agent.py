from google.adk.agents import LlmAgent
import os
import json
import logging
from typing import Dict, Any, Union, Optional
from openai import OpenAI, APIError
import re

logger = logging.getLogger(__name__)

class TestCaseAgent(LlmAgent):
    """
    ADK-based TestCaseAgent using OpenAI via LiteLLM.
    Compatible with ADK Runner for orchestration.
    """
    
    def __init__(self, name: str = "TestCaseAgent"):
        model_name = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")
        super().__init__(
            model=model_name,
            name=name,
            description="Agent for generating comprehensive test cases via ADK + OpenAI",
            instruction="""
You are a senior QA engineer specializing in test case generation. 
Produce comprehensive, high-quality test cases in strict JSON format.

JSON Schema (REQUIRED):
{
  "test_cases": [
    {
      "id": "TC-001",
      "title": "Descriptive title",
      "steps": ["Step 1", "Step 2"],
      "expected_result": "Expected outcome",
      "tags": ["category1"],
      "priority": "high|medium|low"
    }
  ]
}

Requirements:
- Cover positive, negative, edge, and security scenarios.
- Each test case must be independent and executable.
- Steps must be clear, actionable, and verifiable.
- Return ONLY valid JSON; no extra text.
- Avoid duplication; each TC must test distinct functionality.
            """
        )
        logger.info(f"TestCaseAgent initialized with model={model_name} (ADK-compatible)")
    
    async def run_async(self, input_data: dict):
        """
        Async method for ADK Runner compatibility.
        Called by ADK orchestrator.
        """
        spec = input_data.get("spec", "")
        print(f"[TestCaseAgent.run_async] {self.name} processing spec (len={len(spec)})")
        
        # Use sync wrapper internally
        result = generate_test_cases_sync(spec, self)
        return result


# For synchronous wrapper using OpenAI client directly
def generate_test_cases_sync(spec: str, agent: Optional[TestCaseAgent] = None) -> Dict[str, Any]:
    """
    Synchronous test case generation via OpenAI client (LiteLLM style).
    Uses model specified in OPENAI_MODEL env var (default: openai/gpt-4o-mini).
    
    Args:
        spec: Specification text.
        agent: TestCaseAgent instance (optional; used to get model/instruction).
    
    Returns:
        Generated test cases dict with structure {test_cases: [...]}.
    """
    if not spec.strip():
        logger.error("Empty spec provided")
        raise ValueError("Specification cannot be empty")
    
    msg = f"[SYNC_GEN] Sync generation triggered for spec (len={len(spec)})"
    print(msg)
    logger.info(msg)
    
    # Get OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        msg = "[SYNC_GEN] ERROR: OPENAI_API_KEY not set in environment"
        print(msg)
        logger.error(msg)
        raise ValueError("OPENAI_API_KEY environment variable is required")
    print(f"[SYNC_GEN] API key found (first 10 chars: {api_key[:10]}...)")
    
    # Initialize OpenAI client
    print(f"[SYNC_GEN] Initializing OpenAI client...")
    client = OpenAI(api_key=api_key)
    print(f"[SYNC_GEN] OpenAI client initialized")
    
    # Use agent's instruction if available, else fallback
    instruction = agent.instruction if agent else """
You are a senior QA engineer specializing in test case generation. 
Produce comprehensive, high-quality test cases in strict JSON format.

JSON Schema (REQUIRED):
{
  "test_cases": [
    {
      "id": "TC-001",
      "title": "Descriptive title",
      "steps": ["Step 1", "Step 2"],
      "expected_result": "Expected outcome",
      "tags": ["category1"],
      "priority": "high|medium|low"
    }
  ]
}

Requirements:
- Cover positive, negative, edge, and security scenarios.
- Each test case must be independent and executable.
- Steps must be clear, actionable, and verifiable.
- Return ONLY valid JSON; no extra text.
- Avoid duplication; each TC must test distinct functionality.
"""
    
    prompt = f"""{instruction}

SPECIFICATION:
{spec}

Generate comprehensive test cases for the above specification.
Return ONLY valid JSON matching the schema; no extra text."""
    
    try:
        msg = "[SYNC_GEN] Calling OpenAI API (gpt-4o-mini)..."
        print(msg)
        logger.info(msg)
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use direct model name (OpenAI handles this)
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": f"SPECIFICATION:\n{spec}\n\nGenerate comprehensive test cases for the above specification. Return ONLY valid JSON matching the schema; no extra text."}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        raw_response = response.choices[0].message.content.strip()
        msg = f"[SYNC_GEN] OpenAI response received ({len(raw_response)} chars)"
        print(msg)
        logger.info(msg)
        
        # Extract JSON from response (may contain markdown code blocks)
        json_match = re.search(r'\{[\s\S]*\}', raw_response)
        if json_match:
            json_str = json_match.group(0)
            test_cases_dict = json.loads(json_str)
            msg = f"[SYNC_GEN] Parsed {len(test_cases_dict.get('test_cases', []))} test cases from response"
            print(msg)
            logger.info(msg)
            return test_cases_dict
        else:
            msg = "[SYNC_GEN] No JSON found in response, attempting direct parse"
            print(msg)
            logger.warning(msg)
            test_cases_dict = json.loads(raw_response)
            return test_cases_dict
            
    except APIError as e:
        msg = f"[SYNC_GEN] OpenAI API error: {e}"
        print(msg)
        logger.error(msg)
        raise
    except json.JSONDecodeError as e:
        msg = f"[SYNC_GEN] Failed to parse JSON from response: {e}"
        print(msg)
        logger.error(msg)
        logger.debug(f"Raw response: {raw_response[:200]}")
        raise ValueError(f"OpenAI returned invalid JSON: {e}")

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    agent = TestCaseAgent()
    sample_spec = "User login with email and password. Lock after 5 attempts."
    
    # POC: use sync wrapper (not real ADK yet)
    result = generate_test_cases_sync(sample_spec, agent)
    print("Generated:", json.dumps(result, indent=2))
