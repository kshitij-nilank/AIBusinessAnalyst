import json
from pathlib import Path
from typing import Any

from engine.requirement_engine.knowledge_loader import KnowledgeCollection, KnowledgeSection
from engine.requirement_engine.models import RequirementAnalysis
from engine.requirement_engine.orchestrator import (
    LLMCallError,
    PromptBuildError,
    RequirementUnderstandingOrchestrator,
    ResponseParsingError,
)
from engine.requirement_engine.prompt_builder import (
    BuiltPrompt,
    PromptSection,
    PromptSectionName,
)
from engine.requirement_engine.response_parser import RequirementResponseParser
from engine.requirement_engine.validator import RequirementValidator


class FakeKnowledgeLoader:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def load(self, force_reload: bool = False) -> KnowledgeCollection:
        self.calls.append("load")
        return KnowledgeCollection(
            project_root=Path("."),
            documents_by_section={
                KnowledgeSection.BUSINESS: [],
                KnowledgeSection.DATABASE: [],
                KnowledgeSection.REQUIREMENT_ENGINE: [],
                KnowledgeSection.THINKING: [],
            },
        )


class FakePromptBuilder:
    def __init__(self, calls: list[str], prompt: str = "assembled prompt") -> None:
        self.calls = calls
        self.prompt = prompt

    def build(self, **kwargs: Any) -> BuiltPrompt:
        self.calls.append("build")
        return BuiltPrompt(
            prompt=self.prompt,
            sections=(
                PromptSection(
                    name=PromptSectionName.USER_REQUIREMENT,
                    title="Test",
                    content=self.prompt,
                ),
            ),
        )


class FakeLLMClient:
    def __init__(self, calls: list[str], response: str | None = None) -> None:
        self.calls = calls
        self.response = response

    def generate(self, prompt: str) -> str | None:
        self.calls.append("generate")
        return self.response


def _valid_response() -> str:
    return json.dumps(
        {
            "summary": "Complete report requirement",
            "known_information": {
                "season": 2025,
                "sale_range": "14 to 26",
                "area": "AS",
                "category": "CTC",
                "metrics": ["quantity", "value", "average price"],
                "output_grain": "garden-wise",
            },
            "metadata": {"confidence_score": 0.95},
        }
    )


def _orchestrator(calls: list[str], response: str | None = None) -> RequirementUnderstandingOrchestrator:
    return RequirementUnderstandingOrchestrator(
        knowledge_loader=FakeKnowledgeLoader(calls),
        prompt_builder=FakePromptBuilder(calls),
        llm_client=FakeLLMClient(
            calls,
            response=response if response is not None else _valid_response(),
        ),
        response_parser=RequirementResponseParser(),
        requirement_validator=RequirementValidator(),
    )


def test_orchestrator_calls_dependencies_in_order() -> None:
    calls: list[str] = []
    result = _orchestrator(calls).analyze("Need a garden-wise report.")

    assert calls == ["load", "build", "generate"]
    assert isinstance(result, RequirementAnalysis)
    assert result.sql_generation_allowed is True


def test_empty_requirement_raises_prompt_error() -> None:
    calls: list[str] = []
    orchestrator = _orchestrator(calls)

    try:
        orchestrator.analyze(" ")
    except PromptBuildError:
        pass
    else:
        raise AssertionError("Expected PromptBuildError")


def test_empty_llm_response_raises_llm_error() -> None:
    calls: list[str] = []
    orchestrator = _orchestrator(calls, response="")

    try:
        orchestrator.analyze("Need report.")
    except LLMCallError:
        pass
    else:
        raise AssertionError("Expected LLMCallError")


def test_invalid_json_raises_response_parsing_error() -> None:
    calls: list[str] = []
    orchestrator = _orchestrator(calls, response="{bad json")

    try:
        orchestrator.analyze("Need report.")
    except ResponseParsingError:
        pass
    else:
        raise AssertionError("Expected ResponseParsingError")
