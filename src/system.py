import sys
import os
import asyncio

# Add the project root directory to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.adk_orchestrator import ADKTestCaseOrchestrator
from src.agents.google_adk_agent import TestCaseAgent


class IntegratedSystem:
    """High-level wrapper using the ADK orchestrator (v2)."""

    def __init__(self):
        self.orchestrator = ADKTestCaseOrchestrator()
        # Register two ADK agents (Agent1, Agent2)
        self.orchestrator.register_agent(TestCaseAgent("Agent1"))
        self.orchestrator.register_agent(TestCaseAgent("Agent2"))

    def process_specification(self, input_spec: str):
        """Synchronous wrapper that runs the ADK async flow and returns results.

        Input: spec text (string)
        Output: dict with keys: rag_source, results (per-agent test cases)
        """
        print("Processing specification with ADK orchestrator...")
        payload = {"spec": input_spec}
        result = asyncio.run(self.orchestrator.run(payload))
        return result


# Example usage
if __name__ == "__main__":
    system = IntegratedSystem()
    input_spec = (
        "The system should allow users to log in with a username and password.\n"
        "If the credentials are incorrect, an error message should be displayed."
    )
    result = system.process_specification(input_spec)
    print("Orchestration Result:", result)