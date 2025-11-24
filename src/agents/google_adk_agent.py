"""Pure ADK TestCaseAgent definition.

This file now uses the canonical ADK pattern:
- Pydantic input/output schemas
- google.adk.Agent (not direct LlmAgent subclass usage with manual OpenAI calls)
- No direct OpenAI client invocation; model routing is delegated to ADK / LiteLLM layer
- Structured result stored under output_key in session.state via Runner

The orchestration (Runner + session lifecycle) is handled externally by the orchestrator.
"""

import os
import logging
from pydantic import BaseModel
from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
logger = logging.getLogger(__name__)


class TestCaseInput(BaseModel):
    """Input schema for the test case generation agent."""
    spec: str


class SingleTestCase(BaseModel):
    id: str
    title: str
    steps: list[str]
    expected_result: str
    tags: list[str]
    priority: str


class TestCaseOutput(BaseModel):
    """Output schema returned by the agent."""
    test_cases: list[SingleTestCase]
    total_count: int
    coverage_areas: list[str]


def _instruction() -> str:
    return (
        "You are a senior QA engineer specializing in test case generation.\n"
        "Produce comprehensive, high-quality test cases in strict JSON format.\n\n"
        "JSON Structure:\n"
        "{\n  \"test_cases\": [\n    {\n      \"id\": \"TC-001\",\n      \"title\": \"Descriptive title\",\n      \"steps\": [\"Step 1\", \"Step 2\"],\n      \"expected_result\": \"Expected outcome\",\n      \"tags\": [\"category1\"],\n      \"priority\": \"high|medium|low\"\n    }\n  ],\n  \"total_count\": 5,\n  \"coverage_areas\": [\"happy path\", \"error handling\", \"security\"]\n}\n\n"
        "Requirements:\n"
        "- Cover positive, negative, edge, and security scenarios.\n"
        "- Each test case must be independent and executable.\n"
        "- Steps must be clear, actionable, and verifiable.\n"
        "- Return ONLY valid JSON; no extra text.\n"
        "- Avoid duplication; each TC must test distinct functionality."
    )


class TestCaseAgent(Agent):
    """Pure ADK Agent for generating test cases (no direct OpenAI client)."""

    def __init__(self, name: str = "TestCaseAgent"):
        model_name = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")
        super().__init__(
            name=name,
            model=LiteLlm(name=model_name),
            instruction=_instruction(),
            input_schema=TestCaseInput,
            output_schema=TestCaseOutput,
            output_key="generated_test_cases",
            description="Generates structured test cases using ADK Agent + Runner"
        )
        logger.info(f"TestCaseAgent (pure ADK) initialized with model={model_name}")


__all__ = [
    "TestCaseAgent",
    "TestCaseInput",
    "TestCaseOutput",
]
