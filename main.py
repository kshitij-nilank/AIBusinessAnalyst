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

from engine.common.config import load_environment
from engine.common.llm_client import LLMClient, LLMClientError, OfflineRequirementLLMClient
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

        try:
            response = self.client.generate(prompt, json_mode=True)
        except LLMClientError as exc:
            logger.warning(
                "LLM call failed; using offline fallback client. Reason: %s",
                exc,
                extra={
                    "event": "llm_call_offline_fallback",
                    "reason": str(exc),
                },
            )
            return OfflineRequirementLLMClient().generate(prompt)

        status_code = getattr(response, "status_code", 200)
        if isinstance(status_code, int) and status_code >= 400:
            body = _truncate_for_log(getattr(response, "body", ""))
            logger.warning(
                "LLM returned HTTP %s; using offline fallback client. Body: %s",
                status_code,
                body,
                extra={
                    "event": "llm_error_response_offline_fallback",
                    "status_code": status_code,
                    "response_body": body,
                },
            )
            return OfflineRequirementLLMClient().generate(prompt)
        return response


def configure_logging(config: AppConfig) -> None:
    """Initialize process logging."""

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def build_orchestrator() -> RequirementUnderstandingOrchestrator:
    """Create and wire Requirement Understanding Engine dependencies.

    If external LLM configuration is unavailable, an offline fallback client is
    used so the requirement pipeline can still return a blocked structured
    analysis for incomplete requirements.
    """

    try:
        configured_client = LLMClient.from_env()
        logger.info(
            "LLM configured: provider=%s model=%s base_url=%s endpoint=%s api_key_present=%s",
            configured_client.config.provider.value,
            configured_client.config.model,
            configured_client.config.base_url,
            configured_client.endpoint_url,
            bool(configured_client.config.api_key),
            extra={
                "event": "llm_config_loaded",
                "provider": configured_client.config.provider.value,
                "model": configured_client.config.model,
                "base_url": configured_client.config.base_url,
                "endpoint_url": configured_client.endpoint_url,
                "api_key_present": bool(configured_client.config.api_key),
            },
        )
        llm_client = JsonModeLLMClient(configured_client)
    except LLMClientError:
        logger.warning(
            "LLM configuration missing; using offline fallback client.",
            extra={"event": "llm_offline_fallback_enabled"},
        )
        llm_client = OfflineRequirementLLMClient()

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
        except EOFError:
            print("\nApplication closed.")
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
    if analysis.metadata.get("llm_mode") == "offline_fallback":
        print_section(
            "Note",
            "Offline fallback used because LLM API is unavailable.",
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
        "Seasons": ", ".join(str(season) for season in info.seasons)
        if info.seasons
        else None,
        "Sale Range": info.sale_range,
        "Area": info.area,
        "Centre": info.centre,
        "Category": info.category,
        "Tea Type": info.tea_type,
        "Sub Tea Type": info.sub_tea_type,
        "Garden": info.garden,
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


def _truncate_for_log(value: object, limit: int = 2000) -> str:
    """Return a bounded string for diagnostic logs."""

    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...<truncated>"


def main() -> int:
    """Initialize and run the terminal application."""

    load_environment()
    config = AppConfig.from_env()
    configure_logging(config)
    logger.info("Application Started", extra={"event": "application_started"})

    orchestrator = build_orchestrator()
    run_interactive_loop(orchestrator)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
