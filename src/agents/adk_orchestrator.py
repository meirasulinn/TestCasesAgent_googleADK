"""
ADK-based Orchestrator using Tools.
Uses Google ADK's native orchestration with Tools for RAG integration.
"""
import logging
import asyncio
from typing import Dict, Any
from src.agents.google_adk_agent import TestCaseAgent, TestCaseInput
from src.rag.adk_rag_tool import RAGSearchTool, RAGCacheTool
from google.adk import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types

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

        # RAG tools
        self.rag_search_tool = RAGSearchTool()
        self.rag_cache_tool = RAGCacheTool()

        # In-memory ADK services (can be swapped for cloud services later)
        self.session_service = InMemorySessionService()
        self.artifact_service = InMemoryArtifactService()

        logger.info("ADKTestCaseOrchestrator initialized (pure ADK + RAG Tools)")
    
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
        
        # Step 2: Cache miss - invoke agents via Runner (pure ADK)
        msg = "[ADK_ORCHESTRATOR] Cache miss - invoking agents via Runner..."
        print(msg)
        logger.info(msg)

        agent_results = []
        for agent in self.agents:
            print(f"[ADK_ORCHESTRATOR] Preparing Runner for agent {agent.name}...")
            # Create / reuse session id (hash of spec + agent name for determinism)
            session_id = f"sess-{agent.name}-{abs(hash(spec_text)) % (10**8)}"
            session = await self.session_service.create_session(
                app_name="test_case_app",  # logical app name
                user_id="default_user",    # could be provided externally
                session_id=session_id,
            )

            runner = Runner(
                app_name="test_case_app",
                agent=agent,
                session_service=self.session_service,
                artifact_service=self.artifact_service,
            )

            # Build user content
            user_message = types.Content(
                role="user",
                parts=[types.Part(text=spec_text)]
            )

            generated = None
            try:
                print(f"[ADK_ORCHESTRATOR] Running Runner for {agent.name} (session={session_id})...")
                event_count = 0
                async for event in runner.run_async(
                    user_id=session.user_id,
                    session_id=session.id,
                    new_message=user_message,
                ):
                    event_count += 1
                    if event.actions.state_delta.get(agent.output_key):
                        generated = event.actions.state_delta.get(agent.output_key)
                # Fallback: retrieve from stored session state
                if generated is None:
                    stored_session = await self.session_service.get_session(
                        app_name=session.app_name,
                        user_id=session.user_id,
                        session_id=session.id,
                    )
                    if stored_session:
                        generated = stored_session.state.get(agent.output_key)
                if generated:
                    # Normalize to dict form
                    if hasattr(generated, "dict"):
                        generated_dict = generated.dict()
                    else:
                        generated_dict = generated
                    test_cases = [tc for tc in generated_dict.get("test_cases", [])]
                    agent_results.append({
                        "agent": agent.name,
                        "test_cases": test_cases,
                        "total_count": generated_dict.get("total_count", len(test_cases)),
                        "coverage_areas": generated_dict.get("coverage_areas", []),
                        "events": event_count,
                    })
                    print(f"[ADK_ORCHESTRATOR] Agent {agent.name} produced {len(test_cases)} test cases (events={event_count})")
                else:
                    print(f"[ADK_ORCHESTRATOR] Agent {agent.name} returned no structured output")
                    agent_results.append({"agent": agent.name, "error": "No output"})
            except Exception as e:
                print(f"[ADK_ORCHESTRATOR] Agent {agent.name} failed: {e}")
                agent_results.append({"agent": agent.name, "error": str(e)})
        
        # Step 3: Cache results using RAGCacheTool
        print("[ADK_ORCHESTRATOR] Caching results via RAGCacheTool...")
        await self.rag_cache_tool.run_async({"spec": spec_text, "results": agent_results})
        print("[ADK_ORCHESTRATOR] Results cached and indexed")
        return {"rag_source": "generated", "rag_similarity": None, "results": agent_results}
