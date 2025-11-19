from google.adk import Runner
from src.agents.google_adk_agent import TestCaseAgent

class TestCaseOrchestrator:
    def __init__(self):
        self.agent = TestCaseAgent()
        self.agents = []

    def register_agent(self, agent):
        self.agents.append(agent)
        print(f"Agent {agent.name} registered.")

    def run(self, input_spec):
        print("Running orchestrator with input specification...")
        results = []
        for agent in self.agents:
            response = agent.run(input_spec)
            results.append({"agent": agent.name, "response": response})
        return results

# Example usage
if __name__ == "__main__":
    orchestrator = TestCaseOrchestrator()
    input_spec = """
        The system should allow users to log in with a username and password.
        If the credentials are incorrect, an error message should be displayed.
    """
    result = orchestrator.run(input_spec)
    print("Generated Test Cases:", result)