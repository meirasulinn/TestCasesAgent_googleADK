"""
ADK-based Orchestrator using Tools.
Uses Google ADK's native orchestration with Tools for RAG integration.
"""
import logging
import json
from typing import Dict, Any
from src.agents.google_adk_agent import TestCaseAgent
from src.rag.adk_rag_tool import RAGSearchTool, RAGCacheTool

logger = logging.getLogger(__name__)


class ADKTestCaseOrchestrator:
    """
    Pure ADK orchestration using Tools.
    
    Flow:
    1. Spec → RAGSearchTool (check cache + semantic search)
    2. If miss → Invoke agents directly (as LlmAgent subclasses)
    3. If hit → Return cached result
    4. Result → RAGCacheTool (store in Redis + FAISS)
    """
    
    def __init__(self):
        """Initialize ADK orchestrator with RAG tools."""
        self.agents = []
        
        # Register RAG tools
        self.rag_search_tool = RAGSearchTool()
        self.rag_cache_tool = RAGCacheTool()
        
        logger.info("ADKTestCaseOrchestrator initialized with RAG Tools")
    
    def register_agent(self, agent: TestCaseAgent):
        """Register an ADK agent for orchestration."""
        self.agents.append(agent)
        logger.info(f"Agent {agent.name} registered with ADK orchestrator")
    
    async def run(self, input_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrate test case generation using ADK Runner.
        
        Args:
            input_spec: Dict with 'spec' key or string.
        
        Returns:
            Dict with test cases and RAG metadata.
        """
        # Normalize input
        if isinstance(input_spec, dict):
            spec_text = input_spec.get("spec") or str(input_spec)
        else:
            spec_text = str(input_spec)
        
        msg = f"[ADK_ORCHESTRATOR] Received spec (len={len(spec_text)})"
        print(msg)
        logger.info(msg)
        
        # Step 1: Check RAG cache using Tool
        print("[ADK_ORCHESTRATOR] Calling RAGSearchTool...")
        rag_search_result = await self.rag_search_tool.run_async({"spec": spec_text})
        
        # If cache hit, return immediately
        if rag_search_result.get("source") in ["cache", "faiss_cache"]:
            msg = f"[ADK_ORCHESTRATOR] RAG hit (source={rag_search_result['source']}, similarity={rag_search_result.get('similarity')})"
            print(msg)
            logger.info(msg)
            return {
                "rag_source": rag_search_result["source"],
                "rag_similarity": rag_search_result.get("similarity"),
                "results": rag_search_result.get("result", [])
            }
        
        # Step 2: Cache miss - invoke agents
        msg = "[ADK_ORCHESTRATOR] Cache miss - invoking agents..."
        print(msg)
        logger.info(msg)
        
        # Build agent execution sequence
        agent_results = []
        for agent in self.agents:
            msg = f"[ADK_ORCHESTRATOR] Running agent {agent.name}..."
            print(msg)
            logger.info(msg)
            
            # Execute agent asynchronously
            try:
                result = await agent.run_async({"spec": spec_text})
                agent_results.append({
                    "agent": agent.name,
                    "test_cases": result.get("test_cases", [])
                })
                msg = f"[ADK_ORCHESTRATOR] Agent {agent.name} completed: {len(result.get('test_cases', []))} test cases"
                print(msg)
                logger.info(msg)
            except Exception as e:
                msg = f"[ADK_ORCHESTRATOR] Agent {agent.name} failed: {e}"
                print(msg)
                logger.error(msg)
                agent_results.append({"agent": agent.name, "error": str(e)})
        
        # Step 3: Cache results using RAGCacheTool
        print("[ADK_ORCHESTRATOR] Caching results via RAGCacheTool...")
        await self.rag_cache_tool.run_async({
            "spec": spec_text,
            "results": agent_results
        })
        
        msg = "[ADK_ORCHESTRATOR] Results cached and indexed"
        print(msg)
        logger.info(msg)
        
        return {
            "rag_source": "generated",
            "rag_similarity": None,
            "results": agent_results
        }
