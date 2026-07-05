"""Deterministic validation for requirement-analysis readiness.

The validator makes requirement-readiness rules executable for the Requirement
Understanding Engine. It does not call an LLM, read knowledge files, or
generate SQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from engine.requirement_engine.models import (
    ClarificationQuestion,
    KnownInformation,
    MissingInformation,
    QuestionPriority,
    RequirementAnalysis,
    RequirementFieldStatus,
    RequirementStatus,
)


@dataclass(frozen=True, slots=True)
class MandatoryFieldRule:
    """A deterministic rule for one mandatory SQL-readiness field."""

    field_name: str
    question_id: str
    question: str
    related_field: str
    expected_answer_format: str
    is_present: Callable[[KnownInformation, dict[str, object]], bool]


class RequirementValidator:
    """Validate whether a requirement analysis is ready for SQL generation.

    The validator checks mandatory business information, adds blocker
    clarification questions when required, updates the analysis status, and
    records a deterministic confidence score in ``analysis.metadata``.
    """

    MINIMUM_SQL_CONFIDENCE = 0.85
    MISSING_FIELD_PENALTY = 0.12

    def __init__(self, minimum_confidence: float = MINIMUM_SQL_CONFIDENCE) -> None:
        """Create a validator.

        Args:
            minimum_confidence: Minimum confidence required before SQL
                generation can be allowed.
        """

        self.minimum_confidence = minimum_confidence
        self._mandatory_rules = self._build_mandatory_rules()

    def validate(self, analysis: RequirementAnalysis) -> RequirementAnalysis:
        """Validate a ``RequirementAnalysis`` and return an updated copy.

        SQL generation is blocked whenever mandatory information is missing or
        the final confidence score is below the configured threshold.
        """

        updated = analysis.model_copy(deep=True)
        metadata = dict(updated.metadata)

        missing_rules = [
            rule
            for rule in self._mandatory_rules
            if not rule.is_present(updated.known_information, metadata)
        ]

        missing_information = list(updated.missing_information)
        clarification_questions = list(updated.clarification_questions)

        for rule in missing_rules:
            missing_information = self._ensure_missing_information(
                missing_information,
                rule,
            )
            clarification_questions = self._ensure_clarification_question(
                clarification_questions,
                rule,
            )

        confidence_score = self._calculate_confidence(
            metadata=metadata,
            missing_count=len(missing_rules),
        )
        metadata["confidence_score"] = confidence_score
        metadata["minimum_sql_confidence"] = self.minimum_confidence
        metadata["missing_mandatory_fields"] = [
            rule.field_name for rule in missing_rules
        ]

        sql_generation_allowed = (
            not missing_rules and confidence_score >= self.minimum_confidence
        )

        if missing_rules:
            # SQL is blocked because required business filters or output
            # definitions are not yet complete enough to protect correctness.
            status = RequirementStatus.NEEDS_CLARIFICATION
        elif confidence_score < self.minimum_confidence:
            # SQL is blocked because the requirement is complete on paper but
            # the confidence gate says it is still not reliable enough.
            status = RequirementStatus.BLOCKED
        else:
            status = RequirementStatus.READY_FOR_SQL

        return updated.model_copy(
            update={
                "missing_information": missing_information,
                "clarification_questions": clarification_questions,
                "metadata": metadata,
                "sql_generation_allowed": sql_generation_allowed,
                "status": status,
            },
            deep=True,
        )

    def _ensure_missing_information(
        self,
        existing: list[MissingInformation],
        rule: MandatoryFieldRule,
    ) -> list[MissingInformation]:
        """Add a missing-information item unless one already exists."""

        if any(
            self._normalize(item.field_name) == self._normalize(rule.field_name)
            for item in existing
        ):
            return existing

        return [
            *existing,
            MissingInformation(
                field_name=rule.field_name,
                status=RequirementFieldStatus.MISSING,
                reason=(
                    "SQL blocked because this mandatory requirement field is "
                    "missing or unclear."
                ),
                blocks_sql_generation=True,
            ),
        ]

    def _ensure_clarification_question(
        self,
        existing: list[ClarificationQuestion],
        rule: MandatoryFieldRule,
    ) -> list[ClarificationQuestion]:
        """Add a blocker clarification question unless it already exists."""

        normalized_question = self._normalize(rule.question)
        normalized_field = self._normalize(rule.related_field)

        for question in existing:
            if self._normalize(question.question) == normalized_question:
                return existing
            if self._normalize(question.related_field) == normalized_field:
                return existing

        return [
            *existing,
            ClarificationQuestion(
                question_id=rule.question_id,
                question=rule.question,
                priority=QuestionPriority.BLOCKER,
                related_field=rule.related_field,
                expected_answer_format=rule.expected_answer_format,
            ),
        ]

    def _calculate_confidence(
        self,
        *,
        metadata: dict[str, object],
        missing_count: int,
    ) -> float:
        """Calculate deterministic confidence after mandatory-field penalties."""

        base_confidence = self._read_base_confidence(metadata)
        confidence = base_confidence - (missing_count * self.MISSING_FIELD_PENALTY)
        return max(0.0, min(1.0, round(confidence, 4)))

    @staticmethod
    def _read_base_confidence(metadata: dict[str, object]) -> float:
        """Read the starting confidence from metadata, defaulting to 1.0."""

        value = metadata.get("confidence_score", 1.0)
        if isinstance(value, bool):
            return 1.0
        if isinstance(value, (int, float)):
            return max(0.0, min(1.0, float(value)))
        return 1.0

    def _build_mandatory_rules(self) -> tuple[MandatoryFieldRule, ...]:
        """Create mandatory SQL-readiness rules."""

        return (
            MandatoryFieldRule(
                field_name="season_or_financial_year",
                question_id="Q001_Season",
                question="Which season or financial year should be used?",
                related_field="season",
                expected_answer_format="Season year or financial year.",
                is_present=lambda info, metadata: bool(info.season)
                or bool(info.seasons)
                or self._has_metadata_value(metadata, "financial_year"),
            ),
            MandatoryFieldRule(
                field_name="sale_range_or_date_range",
                question_id="Q002_SaleRange",
                question=(
                    "Which sale number, sale range, or date range should be "
                    "considered?"
                ),
                related_field="sale_range",
                expected_answer_format="Sale number, sale range, or date range.",
                is_present=lambda info, metadata: self._has_text(info.sale_range)
                or self._has_metadata_value(metadata, "sale_number")
                or self._has_metadata_value(metadata, "date_range"),
            ),
            MandatoryFieldRule(
                field_name="area_centre_or_scope",
                question_id="Q003_Area",
                question="Which area, centre, or scope should the report cover?",
                related_field="area",
                expected_answer_format="Area, centre, or scope.",
                is_present=lambda info, metadata: self._has_text(info.area)
                or self._has_text(info.centre)
                or self._has_text(info.garden)
                or self._has_text(info.buyer)
                or self._has_metadata_value(metadata, "scope"),
            ),
            MandatoryFieldRule(
                field_name="category_or_tea_type",
                question_id="Q004_Category",
                question="Should the report be for CTC, Orthodox, or all categories?",
                related_field="category",
                expected_answer_format="Category or tea type.",
                is_present=lambda info, metadata: self._has_text(info.category)
                or self._has_text(info.tea_type)
                or self._has_metadata_value(metadata, "category")
                or self._has_metadata_value(metadata, "tea_type"),
            ),
            MandatoryFieldRule(
                field_name="metrics",
                question_id="Q005_Metrics",
                question=(
                    "Which metrics are required: quantity, value, average price, "
                    "buyer count, ranking, or another metric?"
                ),
                related_field="metrics",
                expected_answer_format="Metric list.",
                is_present=lambda info, metadata: bool(info.metrics)
                or self._has_metadata_value(metadata, "metrics"),
            ),
            MandatoryFieldRule(
                field_name="grouping_level",
                question_id="Q006_Grouping",
                question=(
                    "At what level should the report be prepared: garden-wise, "
                    "buyer-wise, sale-wise, grade-wise, or area-wise?"
                ),
                related_field="output_grain",
                expected_answer_format="Grouping level.",
                is_present=lambda info, metadata: self._has_text(info.output_grain)
                or self._has_metadata_value(metadata, "grouping_level"),
            ),
        )

    @staticmethod
    def _has_text(value: str | None) -> bool:
        """Return whether a text field contains meaningful content."""

        return bool(value and value.strip())

    @staticmethod
    def _has_metadata_value(metadata: dict[str, object], key: str) -> bool:
        """Return whether metadata contains a meaningful value for a key."""

        value = metadata.get(key)
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, list | tuple | set | dict):
            return bool(value)
        return True

    @staticmethod
    def _normalize(value: str | None) -> str:
        """Normalize text for duplicate detection."""

        return " ".join((value or "").strip().casefold().split())
