"""
TestCaseAgent - generates test cases from specifications using Google ADK.
Pure ADK implementation following the reference pattern.
"""
import logging
from typing import Dict, Any
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types
from src.agents.base_agent import BaseAgent
from src.services.session_manager import SessionManager
from src.services.faiss_service import FAISSService
from src.config.settings import settings

logger = logging.getLogger(__name__)


class TestCaseAgent(BaseAgent):
    """
    Agent for generating comprehensive test cases using Google ADK.
    
    Uses:
    - Google ADK LlmAgent with LiteLlm model
    - OpenAI via LiteLLM (configured in settings)
    - ADK InMemorySessionService for session management
    - Session-local FAISS for context retrieval
    - Redis for caching results
    """
    
    def __init__(
        self,
        user_id: str,
        session_manager: SessionManager,
        faiss_service: FAISSService
    ):
        super().__init__(
            name="TestCaseAgent",
            user_id=user_id,
            session_manager=session_manager,
            faiss_service=faiss_service
        )
        
        # Create ADK agent (LlmAgent with LiteLlm model)
        self.adk_agent = self.create_adk_agent()
        
        # ADK services (using ADK's built-in session management)
        self.adk_session_service = InMemorySessionService()
        self.adk_artifact_service = InMemoryArtifactService()
        
        logger.info(f"TestCaseAgent created for user {user_id} with model {self.model}")
    
    def create_adk_agent(self) -> LlmAgent:
        """
        Create Google ADK LlmAgent with LiteLlm model.
        Following the reference pattern from test.py.
        
        Returns:
            Configured LlmAgent instance
        """
        instruction = self._get_instruction()
        
        # Create LlmAgent with LiteLlm model (pure ADK pattern)
        agent = LlmAgent(
            model=LiteLlm(model=self.model),  # LiteLlm wrapper for openai/gpt-4o-mini
            name=f"test_case_agent_{self.user_id}",
            instruction=instruction,
            description="Generates comprehensive test cases from specifications"
        )
        
        return agent
    
    def _get_instruction(self) -> str:
        """Get agent instruction prompt."""
        return """You are a senior QA engineer specializing in test case generation.

Your task: Generate comprehensive, high-quality test cases from the provided specification.

Output Format (JSON):
{
  "test_cases": [
    {
      "id": "TC-001",
      "title": "Descriptive title",
      "steps": ["Step 1", "Step 2", ...],
      "expected_result": "Expected outcome",
      "tags": ["functional", "security", ...],
      "priority": "high|medium|low"
    }
  ],
  "total_count": 10,
  "coverage_areas": ["happy path", "error handling", "security", "edge cases"]
}

Requirements:
- Cover positive, negative, edge, and security scenarios
- Each test case must be independent and executable
- Steps must be clear, actionable, and verifiable
- Return valid JSON matching the structure above
- Avoid duplication; each test case tests distinct functionality
- Include priority: high (critical), medium (important), low (nice-to-have)
- Tag test cases appropriately: functional, security, performance, usability, etc.

When you receive a specification, analyze it carefully and generate the test cases accordingly.
"""
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process specification and generate test cases using ADK Runner.
        
        Args:
            input_data: {
                "spec": str - specification text
            }
        
        Returns:
            {
                "test_cases": [...],
                "total_count": int,
                "coverage_areas": [...],
                "source": "generated" | "cache"
            }
        """
        spec_text = input_data.get("spec", "")
        
        if not spec_text.strip():
            logger.error(f"Empty spec provided for user {self.user_id}")
            return {
                "test_cases": [],
                "total_count": 0,
                "coverage_areas": [],
                "error": "Specification cannot be empty"
            }
        
        logger.info(f"Processing spec for user {self.user_id} (len={len(spec_text)})")
        
        # Check cache first
        cache_key = f"test_cases:{hash(spec_text)}"
        cached = await self.get_cache(cache_key)
        if cached:
            logger.info(f"Cache hit for user {self.user_id}")
            cached["source"] = "cache"
            return cached
        
        # Check FAISS for similar specifications
        similar = self.faiss_service.search(spec_text, top_k=1)
        if similar:
            logger.info(f"FAISS hit for user {self.user_id} (similarity={similar[0]['similarity']})")
            # If highly similar AND has valid test cases, return cached result
            if similar[0]['similarity'] > 0.95:
                cached_result = similar[0]['metadata'].get('test_cases', {})
                # Only use cache if it has actual test cases
                if cached_result and cached_result.get('test_cases') and len(cached_result.get('test_cases', [])) > 0:
                    logger.info(f"Returning {len(cached_result['test_cases'])} cached test cases from FAISS")
                    cached_result["source"] = "faiss_cache"
                    return cached_result
                else:
                    logger.info(f"FAISS hit but no valid test cases in cache, will generate new")
        
        # Generate using ADK
        logger.info(f"Generating test cases via ADK for user {self.user_id}")
        result = await self._generate_with_adk(spec_text)
        
        # Cache the result
        await self.set_cache(cache_key, result, ttl=3600)
        
        # Add to FAISS
        self.faiss_service.add_document(
            text=spec_text,
            metadata={"test_cases": result}
        )
        
        result["source"] = "generated"
        return result
    
    async def _generate_with_adk(self, spec_text: str) -> Dict[str, Any]:
        """
        Generate test cases using Google ADK Runner.
        Following the reference pattern from test.py.
        
        Args:
            spec_text: Specification text
        
        Returns:
            Generated test cases
        """
        # Create session for this generation (ADK pattern)
        session_id = f"gen_{self.user_id}_{abs(hash(spec_text)) % (10**8)}"
        session = await self.adk_session_service.create_session(
            app_name=settings.ADK_APP_NAME,
            user_id=self.user_id,
            session_id=session_id
        )
        
        logger.info(f"Created ADK session {session_id} for user {self.user_id}")
        
        # Create Runner (ADK pattern)
        runner = Runner(
            app_name=settings.ADK_APP_NAME,
            agent=self.adk_agent,
            session_service=self.adk_session_service,
            artifact_service=self.adk_artifact_service
        )
        
        # Build user message (ADK pattern)
        user_message = types.Content(
            role='user',
            parts=[types.Part(text=f"SPECIFICATION:\n{spec_text}\n\nGenerate comprehensive test cases in JSON format.")]
        )
        
        # Run agent and collect responses (ADK pattern)
        responses = []
        event_count = 0
        
        try:
            logger.info(f"Starting ADK Runner for user {self.user_id}...")
            async for event in runner.run_async(
                user_id=self.user_id,
                session_id=session_id,
                new_message=user_message
            ):
                event_count += 1
                logger.debug(f"Event {event_count}: author={event.author}, has_content={bool(event.content)}")
                
                # Collect text responses
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            responses.append(part.text)
                            logger.debug(f"Collected response part: {len(part.text)} chars")
            
            logger.info(f"ADK Runner completed: {event_count} events, {len(responses)} response parts")
            
            # Parse the response
            if responses:
                full_response = ' '.join(responses)
                logger.info(f"ADK generated response ({len(full_response)} chars, {event_count} events)")
                
                # Try to extract JSON from response
                import json
                import re
                
                # Look for JSON in the response
                json_match = re.search(r'\{[\s\S]*\}', full_response)
                if json_match:
                    result = json.loads(json_match.group(0))
                    logger.info(f"Parsed {result.get('total_count', 0)} test cases from ADK response")
                    return result
                else:
                    logger.warning(f"No JSON found in ADK response, returning raw text")
                    return {
                        "test_cases": [],
                        "total_count": 0,
                        "coverage_areas": [],
                        "raw_response": full_response
                    }
            else:
                logger.error(f"ADK returned no content for user {self.user_id}")
                return {
                    "test_cases": [],
                    "total_count": 0,
                    "coverage_areas": [],
                    "error": "No content from ADK agent"
                }
        
        except Exception as e:
            logger.error(f"ADK generation failed for user {self.user_id}: {e}")
            return {
                "test_cases": [],
                "total_count": 0,
                "coverage_areas": [],
                "error": str(e)
            }
