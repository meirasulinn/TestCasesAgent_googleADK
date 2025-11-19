import logging
from src.agents.google_adk_agent import TestCaseAgent, generate_test_cases_sync
from src.rag.retrieval import RAGRetriever

logger = logging.getLogger(__name__)

class TestCaseOrchestrator:
    """
    Orchestrates test case generation using ADK agents + RAG layer.
    
    Flow:
    1. Receive spec
    2. Check RAG (Redis/FAISS) for similar cached results
    3. If hit: return cached result
    4. If miss: invoke agents via generate_test_cases_sync
    5. Cache result and return
    
    Note: Full async ADK integration (runner.run_async) to follow in v2.
    """
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6381):
        self.agents = []
        self.rag_retriever = RAGRetriever(redis_host=redis_host, redis_port=redis_port)
        logger.info("TestCaseOrchestrator initialized with RAG layer")
    
    def register_agent(self, agent: TestCaseAgent):
        """Register an ADK agent for orchestration."""
        self.agents.append(agent)
        logger.info(f"Agent {agent.name} registered")
    
    def _generate_test_cases(self, spec: str):
        """Internal: invoke all registered agents and collect results."""
        print(f"[_GENERATE_TEST_CASES] Starting generation for spec (len={len(spec)})")
        results = []
        for agent in self.agents:
            msg = f"[_GENERATE_TEST_CASES] Invoking agent {agent.name}"
            print(msg)
            logger.info(msg)
            try:
                # Use sync wrapper (POC; production would use runner.run_async())
                result = generate_test_cases_sync(spec, agent)
                test_cases = result.get("test_cases", [])
                results.append({
                    "agent": agent.name, 
                    "test_cases": test_cases
                })
                msg = f"[_GENERATE_TEST_CASES] Agent {agent.name} completed: {len(test_cases)} test cases"
                print(msg)
                logger.info(msg)
            except Exception as e:
                msg = f"[_GENERATE_TEST_CASES] Agent {agent.name} failed: {e}"
                print(msg)
                logger.error(msg)
                results.append({"agent": agent.name, "error": str(e)})
        print(f"[_GENERATE_TEST_CASES] Done. Total agents: {len(results)}")
        return results
    
    def run(self, input_spec):
        """
        Orchestrate test case generation:
        1. Check RAG cache
        2. If hit: return cached
        3. If miss: generate via agents + cache result
        
        Args:
            input_spec: Dict with 'spec' key or string.
        
        Returns:
            Dict with RAG metadata and results.
        """
        # Normalize input
        if isinstance(input_spec, dict):
            spec_text = input_spec.get("spec") or str(input_spec)
        else:
            spec_text = str(input_spec)
        
        msg = f"[ORCHESTRATOR] Received spec (len={len(spec_text)})"
        print(msg)
        logger.info(msg)
        
        # RAG lookup: check cache first
        print(f"[ORCHESTRATOR] Calling RAG retriever...")
        rag_result = self.rag_retriever.lookup_or_generate(
            spec_text,
            generator_func=self._generate_test_cases
        )
        
        source = rag_result["source"]
        similarity = rag_result.get("similarity")
        result = rag_result["result"]
        
        msg = f"[ORCHESTRATOR] RAG result: source={source}, similarity={similarity}"
        print(msg)
        logger.info(msg)
        
        return {
            "rag_source": source,
            "rag_similarity": similarity,
            "results": result
        }

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    orchestrator = TestCaseOrchestrator()
    agent1 = TestCaseAgent("Agent1")
    agent2 = TestCaseAgent("Agent2")
    orchestrator.register_agent(agent1)
    orchestrator.register_agent(agent2)
    
    spec = "User authentication: email + password login with 5-attempt lockout"
    result = orchestrator.run(spec)
    print("Orchestration result:", result)
