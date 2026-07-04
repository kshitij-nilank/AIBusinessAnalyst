"""Command-line entry point for AI Business Analyst.

This module wires the Requirement Understanding Engine together and provides a
simple interactive terminal loop. It does not contain business rules, prompt
engineering, validation rules, SQL generation, or provider-specific reasoning.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from engine.common.llm_client import LLMClient, LLMClientError
from engine.requirement_engine.knowledge_loader import KnowledgeLoader
from engine.requirement_engine.models import RequirementAnalysis
from engine.requirement_engine.orchestrator import (
    RequirementOrchestratorError,
    RequirementUnderstandingOrchestrator,
)
from engine.requirement_engine.prompt_builder import PromptBuilder
from engine.requirement_engine.response_parser import RequirementResponseParser
from engine.requirement_engine.validator import RequirementValidator


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Application-level runtime configuration."""

    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load application configuration from environment variables."""

        return cls(log_level=os.getenv("AIBA_LOG_LEVEL", "INFO"))


class JsonModeLLMClient:
    """Adapter that requests JSON output from the configured LLM client."""

    def __init__(self, client: LLMClient) -> None:
        """Create an adapter for an existing LLM client."""

        self.client = client

    def generate(self, prompt: str) -> Any:
        """Generate a raw JSON-mode LLM response for the orchestrator."""

        return self.client.generate(prompt, json_mode=True)


def configure_logging(config: AppConfig) -> None:
    """Initialize process logging."""

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def build_orchestrator() -> RequirementUnderstandingOrchestrator:
    """Create and wire Requirement Understanding Engine dependencies.

    Raises:
        LLMClientError: If required LLM environment configuration is missing.
    """

    llm_client = JsonModeLLMClient(LLMClient.from_env())
    return RequirementUnderstandingOrchestrator(
        knowledge_loader=KnowledgeLoader(),
        prompt_builder=PromptBuilder(),
        llm_client=llm_client,
        response_parser=RequirementResponseParser(),
        requirement_validator=RequirementValidator(),
    )


def run_interactive_loop(
    orchestrator: RequirementUnderstandingOrchestrator,
) -> None:
    """Accept requirements from the terminal until the user exits."""

    print_banner()
    prompt = "Enter a requirement (or type 'exit' to quit): "

    while True:
        try:
            requirement = input(prompt).strip()
        except KeyboardInterrupt:
            print("\nApplication interrupted. Closing.")
            logger.info("Application Closed", extra={"event": "application_closed"})
            return

        if requirement.casefold() in {"exit", "quit"}:
            print("Application closed.")
            logger.info("Application Closed", extra={"event": "application_closed"})
            return

        if not requirement:
            print("Please enter a requirement, or type 'exit' to quit.")
            prompt = "Enter another requirement (or type 'exit' to quit): "
            continue

        logger.info("Requirement Received", extra={"event": "requirement_received"})
        try:
            analysis = orchestrator.analyze(requirement)
        except RequirementOrchestratorError as exc:
            print(f"Could not analyze the requirement: {exc}")
        except Exception:
            logger.exception(
                "Unexpected application error.",
                extra={"event": "unexpected_application_error"},
            )
            print("An unexpected error occurred while analyzing the requirement.")
        else:
            if not isinstance(analysis, RequirementAnalysis):
                print("The engine returned an invalid analysis object.")
            else:
                display_analysis(analysis)
                logger.info(
                    "Analysis Completed",
                    extra={
                        "event": "analysis_completed",
                        "sql_generation_allowed": analysis.sql_generation_allowed,
                    },
                )

        prompt = "Enter another requirement (or type 'exit' to quit): "


def print_banner() -> None:
    """Print the application banner."""

    print("=" * 50)
    print("AI BUSINESS ANALYST")
    print("=" * 50)


def display_analysis(analysis: RequirementAnalysis) -> None:
    """Display a human-readable requirement analysis."""

    print("\n" + "=" * 50)
    print("AI BUSINESS ANALYST")
    print("=" * 50)
    print_section("Requirement Summary", analysis.summary)
    print_section(
        "Business Objective",
        analysis.known_information.business_objective or "Unknown",
    )
    print_section("Known Information", format_known_information(analysis))
    print_section("Missing Information", format_missing_information(analysis))
    print_section(
        "Clarification Questions",
        format_clarification_questions(analysis),
    )
    print_section(
        "Applicable Business Rules",
        format_business_rules(analysis),
    )
    print_section(
        "Candidate Database Objects",
        format_candidate_database_objects(analysis),
    )
    print_section(
        "Confidence Score",
        str(analysis.metadata.get("confidence_score", "Unknown")),
    )
    print_section(
        "SQL Generation Status",
        "Allowed" if analysis.sql_generation_allowed else "Blocked",
    )
    print("=" * 50)


def print_section(title: str, content: str) -> None:
    """Print one titled output section."""

    print(f"\n{title}")
    print("-" * len(title))
    print(content or "Unknown")


def format_known_information(analysis: RequirementAnalysis) -> str:
    """Format known requirement fields for terminal display."""

    info = analysis.known_information
    rows = {
        "Stakeholder": info.stakeholder,
        "Report Type": info.report_type,
        "Season": info.season,
        "Sale Range": info.sale_range,
        "Area": info.area,
        "Centre": info.centre,
        "Category": info.category,
        "Tea Type": info.tea_type,
        "Sub Tea Type": info.sub_tea_type,
        "EST/BLF": info.est_blf,
        "Lot Status": info.lot_status,
        "Metrics": ", ".join(info.metrics) if info.metrics else None,
        "Grouping Level": info.output_grain,
        "Output Format": info.output_format,
    }
    return format_key_value_rows(rows)


def format_missing_information(analysis: RequirementAnalysis) -> str:
    """Format missing information records."""

    if not analysis.missing_information:
        return "None"
    return "\n".join(
        f"- {item.field_name}: {item.reason}"
        for item in analysis.missing_information
    )


def format_clarification_questions(analysis: RequirementAnalysis) -> str:
    """Format clarification questions."""

    if not analysis.clarification_questions:
        return "None"
    return "\n".join(
        f"- [{question.priority.value}] {question.question}"
        for question in analysis.clarification_questions
    )


def format_business_rules(analysis: RequirementAnalysis) -> str:
    """Format applicable business-rule references."""

    if not analysis.business_rules:
        return "Unknown"
    return "\n".join(
        f"- {rule.rule_id or 'Unnumbered'}: {rule.name} ({rule.status.value})"
        for rule in analysis.business_rules
    )


def format_candidate_database_objects(analysis: RequirementAnalysis) -> str:
    """Format candidate database objects."""

    if not analysis.candidate_database_objects:
        return "Unknown"
    return "\n".join(
        f"- {obj.object_name} ({obj.object_type.value}): {obj.purpose}"
        for obj in analysis.candidate_database_objects
    )


def format_key_value_rows(rows: dict[str, object | None]) -> str:
    """Format key-value rows while hiding empty values as Unknown."""

    return "\n".join(
        f"- {key}: {value if value not in (None, '') else 'Unknown'}"
        for key, value in rows.items()
    )


def main() -> int:
    """Initialize and run the terminal application."""

    config = AppConfig.from_env()
    configure_logging(config)
    logger.info("Application Started", extra={"event": "application_started"})

    try:
        orchestrator = build_orchestrator()
    except LLMClientError as exc:
        print("The LLM client is not configured.")
        print(str(exc))
        print("Configure LLM_PROVIDER, LLM_BASE_URL, LLM_MODEL, and LLM_API_KEY if required.")
        logger.error("Application startup failed.", extra={"event": "startup_failed"})
        return 1

    run_interactive_loop(orchestrator)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
