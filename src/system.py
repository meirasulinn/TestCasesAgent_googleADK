import sys
import os

# Add the project root directory to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag.redis_client import RedisClient
from src.rag.faiss_index import FaissIndex
from src.agents.test_case_orchestrator import TestCaseOrchestrator

class IntegratedSystem:
    def __init__(self):
        self.redis_client = RedisClient()
        self.faiss_index = FaissIndex(dimension=128)
        self.orchestrator = TestCaseOrchestrator()

    def process_specification(self, input_spec):
        print("Processing specification...")

        # Store input in Redis
        self.redis_client.set("input_spec", input_spec)

        # Generate test cases using orchestrator
        test_cases = self.orchestrator.run(input_spec)

        # Index test cases in FAISS
        vectors = self._convert_to_vectors(test_cases)
        self.faiss_index.add_vectors(vectors)

        return test_cases

    def _convert_to_vectors(self, test_cases):
        # Dummy implementation for converting test cases to vectors
        import numpy as np
        return np.random.random((len(test_cases), 128)).astype('float32')

# Example usage
if __name__ == "__main__":
    system = IntegratedSystem()
    input_spec = """
        The system should allow users to log in with a username and password.
        If the credentials are incorrect, an error message should be displayed.
    """
    test_cases = system.process_specification(input_spec)
    print("Generated Test Cases:", test_cases)