"""Requirement Understanding Engine orchestrator.

The orchestrator coordinates the requirement-understanding workflow:

User Requirement -> Knowledge Loader -> Prompt Builder -> LLM Client ->
Response Parser -> Requirement Validator -> RequirementAnalysis

This module intentionally contains no business rules, prompt text, markdown
parsing, SQL generation, provider-specific LLM code, or validation logic. All
dependencies are injected so the workflow can be reused by future engines.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from engine.requirement_engine.knowledge_loader import (
    KnowledgeCollection,
    KnowledgeSection,
)
from engine.requirement_engine.models import RequirementAnalysis
from engine.requirement_engine.prompt_builder import BuiltPrompt
from engine.requirement_engine.response_parser import ParsedRequirementAnalysis


logger = logging.getLogger(__name__)


class RequirementOrchestratorError(RuntimeError):
    """Base exception for Requirement Understanding orchestration failures."""


class KnowledgeLoadingError(RequirementOrchestratorError):
    """Raised when knowledge cannot be loaded into a usable collection."""


class PromptBuildError(RequirementOrchestratorError):
    """Raised when prompt construction fails or returns an empty prompt."""


class LLMCallError(RequirementOrchestratorError):
    """Raised when the LLM dependency fails or returns an empty response."""


class ResponseParsingError(RequirementOrchestratorError):
    """Raised when the LLM response cannot be parsed into a valid model."""


class RequirementValidationError(RequirementOrchestratorError):
    """Raised when the validator dependency fails."""


class KnowledgeLoaderProtocol(Protocol):
    """Dependency contract for loading organized knowledge."""

    def load(self, force_reload: bool = False) -> KnowledgeCollection:
        """Load and return project knowledge."""


class PromptBuilderProtocol(Protocol):
    """Dependency contract for building final prompts."""

    def build(
        self,
        user_requirement: str,
        business_rules: list[Any],
        database_knowledge: list[Any],
        thinking_layer: list[Any],
        requirement_engine_knowledge: list[Any] = ...,
    ) -> BuiltPrompt:
        """Build and return a prompt object."""


class LLMClientProtocol(Protocol):
    """Dependency contract for LLM clients.

    Future clients should expose ``generate``. The current local client exposes
    ``complete``; the orchestrator supports both while keeping the dependency
    replaceable.
    """


class ResponseParserProtocol(Protocol):
    """Dependency contract for parsing raw LLM responses."""

    def parse(self, response: Any) -> ParsedRequirementAnalysis | RequirementAnalysis:
        """Parse raw LLM output."""


class RequirementValidatorProtocol(Protocol):
    """Dependency contract for validating parsed requirement analysis."""

    def validate(self, analysis: RequirementAnalysis) -> RequirementAnalysis:
        """Validate and return an updated requirement analysis."""


class RequirementUnderstandingOrchestrator:
    """Coordinate the Requirement Understanding Engine workflow.

    The orchestrator is intentionally thin. It delegates all specialized work
    to injected dependencies and only enforces the pipeline order, error
    boundaries, and structured logging.
    """

    def __init__(
        self,
        knowledge_loader: KnowledgeLoaderProtocol,
        prompt_builder: PromptBuilderProtocol,
        llm_client: LLMClientProtocol,
        response_parser: ResponseParserProtocol,
        requirement_validator: RequirementValidatorProtocol,
    ) -> None:
        """Create an orchestrator with fully injected dependencies.

        Args:
            knowledge_loader: Component that loads project knowledge.
            prompt_builder: Component that assembles the final LLM prompt.
            llm_client: Component that calls the configured LLM.
            response_parser: Component that parses LLM JSON into models.
            requirement_validator: Component that validates SQL readiness.
        """

        self.knowledge_loader = knowledge_loader
        self.prompt_builder = prompt_builder
        self.llm_client = llm_client
        self.response_parser = response_parser
        self.requirement_validator = requirement_validator

    def analyze(self, requirement: str) -> RequirementAnalysis:
        """Analyze a plain-text business requirement.

        The method executes the workflow in this exact order:
        1. Load knowledge.
        2. Build prompt.
        3. Call LLM.
        4. Parse response.
        5. Validate parsed analysis.
        6. Return final ``RequirementAnalysis``.

        Args:
            requirement: Plain-text stakeholder requirement.

        Returns:
            Final validated ``RequirementAnalysis``.

        Raises:
            PromptBuildError: If the input or built prompt is empty.
            KnowledgeLoadingError: If knowledge loading returns no usable object.
            LLMCallError: If the LLM call fails or returns an empty response.
            ResponseParsingError: If parsing or schema validation fails.
            RequirementValidationError: If validation fails unexpectedly.
            RequirementOrchestratorError: For unexpected orchestration failures.
        """

        if not requirement or not requirement.strip():
            raise PromptBuildError("Requirement text cannot be empty.")

        try:
            knowledge = self._load_knowledge()
            prompt = self._build_prompt(requirement=requirement, knowledge=knowledge)
            raw_response = self._call_llm(prompt=prompt)
            parsed_analysis = self._parse_response(raw_response)
            final_analysis = self._validate_analysis(parsed_analysis)
        except RequirementOrchestratorError:
            raise
        except Exception as exc:
            logger.exception(
                "Unexpected requirement orchestration failure.",
                extra={"event": "requirement_orchestration_unexpected_error"},
            )
            raise RequirementOrchestratorError(
                "Unexpected requirement orchestration failure."
            ) from exc

        logger.info(
            "Requirement analysis completed.",
            extra={
                "event": "requirement_analysis_completed",
                "sql_generation_allowed": final_analysis.sql_generation_allowed,
                "status": final_analysis.status.value,
            },
        )
        return final_analysis

    def _load_knowledge(self) -> KnowledgeCollection:
        """Load knowledge using the injected loader."""

        logger.info(
            "Loading knowledge.",
            extra={"event": "requirement_knowledge_loading"},
        )
        try:
            knowledge = self.knowledge_loader.load()
        except Exception as exc:
            raise KnowledgeLoadingError("Failed to load knowledge.") from exc

        if knowledge is None:
            raise KnowledgeLoadingError("Knowledge loader returned no collection.")

        if knowledge.errors:
            logger.warning(
                "Knowledge loaded with non-fatal errors.",
                extra={
                    "event": "requirement_knowledge_loaded_with_errors",
                    "error_count": len(knowledge.errors),
                },
            )

        logger.info(
            "Knowledge loaded.",
            extra={
                "event": "requirement_knowledge_loaded",
                "document_count": len(knowledge.documents),
                "missing_path_count": len(knowledge.missing_paths),
            },
        )
        return knowledge

    def _build_prompt(
        self,
        *,
        requirement: str,
        knowledge: KnowledgeCollection,
    ) -> BuiltPrompt:
        """Build the final prompt using the injected prompt builder."""

        logger.info(
            "Building prompt.",
            extra={"event": "requirement_prompt_building"},
        )
        try:
            prompt = self.prompt_builder.build(
                user_requirement=requirement,
                business_rules=knowledge.get_section(KnowledgeSection.BUSINESS),
                database_knowledge=knowledge.get_section(KnowledgeSection.DATABASE),
                thinking_layer=knowledge.get_section(KnowledgeSection.THINKING),
                requirement_engine_knowledge=knowledge.get_section(
                    KnowledgeSection.REQUIREMENT_ENGINE
                ),
            )
        except Exception as exc:
            raise PromptBuildError("Failed to build requirement prompt.") from exc

        if prompt is None or not prompt.prompt.strip():
            raise PromptBuildError("Prompt builder returned an empty prompt.")

        logger.info(
            "Prompt built.",
            extra={
                "event": "requirement_prompt_built",
                "prompt_length": len(prompt.prompt),
                "section_count": len(prompt.sections),
            },
        )
        return prompt

    def _call_llm(self, *, prompt: BuiltPrompt) -> Any:
        """Call the injected LLM client and return the raw response."""

        logger.info(
            "Calling LLM.",
            extra={"event": "requirement_llm_calling"},
        )
        try:
            if hasattr(self.llm_client, "generate"):
                raw_response = self.llm_client.generate(prompt.prompt)
            elif hasattr(self.llm_client, "complete"):
                raw_response = self.llm_client.complete(
                    prompt.prompt,
                    json_mode=True,
                )
            else:
                raise LLMCallError(
                    "LLM client must expose generate(prompt) or complete(prompt)."
                )
        except RequirementOrchestratorError:
            raise
        except Exception as exc:
            raise LLMCallError("LLM call failed.") from exc

        if self._is_empty_response(raw_response):
            raise LLMCallError("LLM returned an empty response.")

        logger.info(
            "LLM response received.",
            extra={"event": "requirement_llm_response_received"},
        )
        return raw_response

    def _parse_response(self, raw_response: Any) -> RequirementAnalysis:
        """Parse raw LLM output into ``RequirementAnalysis``."""

        logger.info(
            "Parsing response.",
            extra={"event": "requirement_response_parsing"},
        )
        try:
            parsed = self.response_parser.parse(raw_response)
        except Exception as exc:
            raise ResponseParsingError("Response parser failed.") from exc

        if isinstance(parsed, RequirementAnalysis):
            analysis = parsed
            errors: list[Any] = []
        else:
            analysis = parsed.analysis
            errors = list(parsed.errors)

        if analysis is None or errors:
            raise ResponseParsingError(
                self._format_parse_errors(errors)
                or "Response could not be parsed into RequirementAnalysis."
            )

        logger.info(
            "Response parsed.",
            extra={"event": "requirement_response_parsed"},
        )
        return analysis

    def _validate_analysis(self, analysis: RequirementAnalysis) -> RequirementAnalysis:
        """Validate parsed analysis using the injected validator."""

        logger.info(
            "Validating result.",
            extra={"event": "requirement_result_validating"},
        )
        try:
            validated = self.requirement_validator.validate(analysis)
        except Exception as exc:
            raise RequirementValidationError("Requirement validation failed.") from exc

        if validated is None:
            raise RequirementValidationError("Validator returned no analysis.")

        logger.info(
            "Result validated.",
            extra={
                "event": "requirement_result_validated",
                "sql_generation_allowed": validated.sql_generation_allowed,
                "status": validated.status.value,
            },
        )
        return validated

    @staticmethod
    def _is_empty_response(raw_response: Any) -> bool:
        """Return whether a raw LLM response has no usable body/content."""

        if raw_response is None:
            return True
        if isinstance(raw_response, str | bytes):
            return not raw_response.strip()

        body = getattr(raw_response, "body", None)
        if isinstance(body, str):
            return not body.strip()
        if isinstance(body, bytes):
            return not body.strip()

        return False

    @staticmethod
    def _format_parse_errors(errors: list[Any]) -> str:
        """Return a concise parser error message."""

        if not errors:
            return ""

        formatted: list[str] = []
        for error in errors:
            message = getattr(error, "message", str(error))
            location = getattr(error, "location", None)
            formatted.append(f"{location}: {message}" if location else message)
        return "Response parsing failed: " + "; ".join(formatted)


RequirementEngineOrchestrator = RequirementUnderstandingOrchestrator
