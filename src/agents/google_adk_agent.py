from google.adk.agents import LlmAgent
import re
import os
import json
from typing import List, Dict, Any, Union

try:
    from openai import OpenAI  # openai>=1.x SDK
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

class TestCaseAgent(LlmAgent):
    def __init__(self, name: str = "TestCaseAgent"):
        super().__init__(
            model="gemini-2.0-flash",
            name=name,
            description="Agent for generating test cases",
            instruction="""
You are a test case generation agent. Given a software/product specification text, produce a structured JSON
object with comprehensive test coverage. Follow this schema strictly:
{
  "test_cases": [
    {
      "id": "TC-001",
      "title": "Short title summarizing intent",
      "steps": ["Step 1", "Step 2"],
      "expected_result": "Result after completing steps",
      "tags": ["functional", "login"],
      "priority": "high|medium|low"
    }
  ]
}
Return ONLY JSON. If the spec is ambiguous, still infer plausible edge cases.
            """
        )

    def run(self, spec: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Generate test cases using OpenAI if available; otherwise fallback heuristics.

        Accepts a raw spec string or a dict containing 'spec'.
        """
        # Normalize spec text
        if isinstance(spec, dict):
            spec_text = spec.get("spec") or json.dumps(spec, ensure_ascii=False)
        else:
            spec_text = str(spec or "")

        # Prefer OpenAI when available
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and OpenAI is not None and spec_text.strip():
            client = OpenAI()
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            system_prompt = (
                "You are a senior QA engineer. Generate comprehensive, deduplicated, "
                "and structured test cases in strict JSON. Cover positive, negative, "
                "edge, and security scenarios when relevant."
            )
            user_prompt = (
                "Create test cases for the following specification. Return ONLY JSON with the schema:\n"
                "{\n  \"test_cases\": [\n    {\n      \"id\": \"TC-001\",\n      \"title\": \"...\",\n      \"steps\": [\"Step 1\", \"Step 2\"],\n      \"expected_result\": \"...\",\n      \"tags\": [\"login\", \"negative\"],\n      \"priority\": \"high|medium|low\"\n    }\n  ]\n}\n\n"
                f"Specification:\n{spec_text}"
            )
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )
            content = completion.choices[0].message.content or "{}"
            # Try parse JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Attempt to extract JSON snippet
                start = content.find('{')
                end = content.rfind('}')
                if start != -1 and end != -1 and end > start:
                    try:
                        data = json.loads(content[start : end + 1])
                    except Exception:
                        data = {"test_cases": []}
                else:
                    data = {"test_cases": []}
            return {"status": "success", **data}

        # Heuristic fallback when OpenAI not available or spec empty
        cleaned = re.sub(r"\s+", " ", spec_text.strip())
        if not cleaned:
            return {"test_cases": []}

        # Split into candidate requirement sentences.
        raw_sentences = re.split(r"(?<=[.!?])\s+|\n+|;", cleaned)
        sentences = [s.strip() for s in raw_sentences if s.strip()]

        cases: List[Dict[str, Any]] = []
        for idx, sentence in enumerate(sentences, start=1):
            # Derive a simple title.
            title = sentence[:80]
            steps = self._derive_steps(sentence)
            expected = self._derive_expected(sentence)
            tags = self._infer_tags(sentence)
            priority = self._infer_priority(sentence)
            case = {
                "id": f"TC-{idx:03d}",
                "title": title,
                "steps": steps,
                "expected_result": expected,
                "tags": tags,
                "priority": priority,
            }
            cases.append(case)
        return {"test_cases": cases}

    def _derive_steps(self, sentence: str) -> List[str]:
        # Simple heuristic expansion.
        steps: List[str] = []
        lowered = sentence.lower()
        if "login" in lowered or "log in" in lowered:
            steps.extend([
                "Navigate to login page",
                "Enter valid username",
                "Enter valid password",
                "Click login",
            ])
            if "incorrect" in lowered or "invalid" in lowered:
                steps.append("Enter invalid password and attempt login")
        if "lock" in lowered:
            steps.append("Repeat failed login until lock condition triggers")
        if not steps:
            steps.append(f"Interact: {sentence[:60]}")
        return steps

    def _derive_expected(self, sentence: str) -> str:
        lowered = sentence.lower()
        if "incorrect" in lowered or "invalid" in lowered:
            return "System displays an authentication error message"
        if "lock" in lowered:
            return "Account access is blocked after threshold reached"
        if "login" in lowered:
            return "User is authenticated and redirected to dashboard"
        return "Behavior matches specification without errors"

    def _infer_tags(self, sentence: str) -> List[str]:
        tags = []
        l = sentence.lower()
        if "login" in l:
            tags.append("login")
        if "password" in l:
            tags.append("security")
        if "error" in l or "invalid" in l:
            tags.append("error-handling")
        if "lock" in l:
            tags.append("lockout")
        if not tags:
            tags.append("general")
        return tags

    def _infer_priority(self, sentence: str) -> str:
        l = sentence.lower()
        if any(k in l for k in ["security", "password", "lock", "login"]):
            return "high"
        if any(k in l for k in ["error", "validation"]):
            return "medium"
        return "low"

# Example usage
if __name__ == "__main__":
    agent = TestCaseAgent()
    input_spec = """
        The system should allow users to log in with a username and password.
        If the credentials are incorrect, an error message should be displayed.
    """
    response = agent.run(input_spec)
    print(response)