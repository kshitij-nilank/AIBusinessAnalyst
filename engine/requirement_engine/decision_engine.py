"""Final SQL-readiness decision engine for requirement analysis.

The decision engine does not generate SQL. It applies deterministic gates after
requirement validation, business-rule resolution, and database resolution.
"""

from __future__ import annotations

from engine.requirement_engine.models import (
    ClarificationQuestion,
    DecisionStatus,
    MissingInformation,
    QuestionPriority,
    RequirementAnalysis,
    RequirementStatus,
)


class DecisionEngine:
    """Decide whether a requirement may proceed to SQL generation."""

    MINIMUM_CONFIDENCE = 0.85

    def __init__(self, minimum_confidence: float = MINIMUM_CONFIDENCE) -> None:
        """Create a decision engine.

        Args:
            minimum_confidence: Minimum confidence required to allow SQL.
        """

        self.minimum_confidence = minimum_confidence

    def decide(self, analysis: RequirementAnalysis) -> RequirementAnalysis:
        """Return a requirement analysis with final decision fields updated."""

        blocking_missing = [
            item for item in analysis.missing_information if item.blocks_sql_generation
        ]
        blocker_questions = [
            question
            for question in analysis.clarification_questions
            if question.priority == QuestionPriority.BLOCKER
        ]
        analysis = self._apply_confidence_adjustment(
            analysis=analysis,
            blocking_missing=blocking_missing,
            blocker_questions=blocker_questions,
        )
        confidence_score = self._confidence_score(analysis)

        if blocking_missing:
            return self._blocked_for_missing_information(analysis, blocking_missing)

        if blocker_questions:
            return self._copy_with_decision(
                analysis=analysis,
                decision_status=DecisionStatus.SQL_BLOCKED,
                reason=(
                    "Blocker clarification questions remain unanswered, so SQL "
                    "generation cannot safely proceed."
                ),
                next_action=blocker_questions[0].question,
                sql_generation_allowed=False,
                status=RequirementStatus.NEEDS_CLARIFICATION,
            )

        if confidence_score < self.minimum_confidence:
            return self._copy_with_decision(
                analysis=analysis,
                decision_status=DecisionStatus.SQL_BLOCKED,
                reason=(
                    f"Confidence score {confidence_score:.2f} is below the "
                    f"minimum required score of {self.minimum_confidence:.2f}."
                ),
                next_action=(
                    "Review the extracted requirement and ask clarification "
                    "questions before SQL generation."
                ),
                sql_generation_allowed=False,
                status=RequirementStatus.BLOCKED,
            )

        if not analysis.candidate_database_objects:
            return self._copy_with_decision(
                analysis=analysis,
                decision_status=DecisionStatus.SQL_BLOCKED,
                reason=(
                    "No candidate database objects were identified for the "
                    "requirement."
                ),
                next_action=(
                    "Review database_schema.md or add database knowledge before "
                    "SQL generation."
                ),
                sql_generation_allowed=False,
                status=RequirementStatus.BLOCKED,
            )

        if not analysis.business_rules:
            return self._copy_with_decision(
                analysis=analysis,
                decision_status=DecisionStatus.SQL_BLOCKED,
                reason=(
                    "No applicable business rules were identified for the "
                    "requirement."
                ),
                next_action=(
                    "Resolve applicable business rules before SQL generation."
                ),
                sql_generation_allowed=False,
                status=RequirementStatus.BLOCKED,
            )

        return self._copy_with_decision(
            analysis=analysis,
            decision_status=DecisionStatus.SQL_ALLOWED,
            reason=(
                "Requirement has mandatory business information, applicable "
                "business rules, candidate database objects, and sufficient "
                "confidence."
            ),
            next_action="Proceed to SQL Generation Engine.",
            sql_generation_allowed=True,
            status=RequirementStatus.READY_FOR_SQL,
        )

    def _blocked_for_missing_information(
        self,
        analysis: RequirementAnalysis,
        missing_information: list[MissingInformation],
    ) -> RequirementAnalysis:
        """Return a blocked decision for mandatory missing information."""

        first_missing = missing_information[0]
        return self._copy_with_decision(
            analysis=analysis,
            decision_status=DecisionStatus.SQL_BLOCKED,
            reason=self._missing_reason(first_missing),
            next_action=self._missing_next_action(first_missing),
            sql_generation_allowed=False,
            status=RequirementStatus.NEEDS_CLARIFICATION,
        )

    @staticmethod
    def _missing_reason(missing: MissingInformation) -> str:
        """Return a business-facing reason for one missing field."""

        field_name = missing.field_name
        reasons = {
            "season_or_financial_year": (
                "Season or financial year is missing, so SQL cannot safely "
                "apply the correct period filter."
            ),
            "sale_range_or_date_range": (
                "Sale range, sale number, or date range is missing, so SQL "
                "cannot safely apply the correct time scope."
            ),
            "area_centre_or_scope": (
                "Area, centre, or scope is missing, so SQL cannot safely apply "
                "the correct report boundary."
            ),
            "category_or_tea_type": (
                "Category or tea type is missing, so SQL cannot safely apply "
                "the correct filter."
            ),
            "metrics": (
                "Required metrics are missing, so SQL cannot determine the "
                "correct calculations."
            ),
            "grouping_level": (
                "Grouping level is missing, so SQL cannot determine the output "
                "grain."
            ),
        }
        return reasons.get(
            field_name,
            f"{field_name} is missing or unclear, so SQL generation is blocked.",
        )

    @staticmethod
    def _missing_next_action(missing: MissingInformation) -> str:
        """Return the next action for one missing field."""

        field_name = missing.field_name
        next_actions = {
            "season_or_financial_year": (
                "Ask stakeholder which season or financial year should be used."
            ),
            "sale_range_or_date_range": (
                "Ask stakeholder which sale number, sale range, or date range "
                "should be considered."
            ),
            "area_centre_or_scope": (
                "Ask stakeholder which area, centre, or scope the report should "
                "cover."
            ),
            "category_or_tea_type": (
                "Ask stakeholder whether the report is for CTC, Orthodox, or "
                "all categories."
            ),
            "metrics": (
                "Ask stakeholder which metrics are required: quantity, value, "
                "average price, buyer count, ranking, or another metric."
            ),
            "grouping_level": (
                "Ask stakeholder whether the report should be garden-wise, "
                "buyer-wise, sale-wise, grade-wise, or area-wise."
            ),
        }
        return next_actions.get(
            field_name,
            "Ask stakeholder to clarify the missing requirement field.",
        )

    def _confidence_score(self, analysis: RequirementAnalysis) -> float:
        """Read confidence score from metadata with a safe default."""

        value = analysis.metadata.get("confidence_score", 0.0)
        if isinstance(value, bool):
            return 0.0
        if isinstance(value, (int, float)):
            return max(0.0, min(1.0, float(value)))
        return 0.0

    def _apply_confidence_adjustment(
        self,
        *,
        analysis: RequirementAnalysis,
        blocking_missing: list[MissingInformation],
        blocker_questions: list[ClarificationQuestion],
    ) -> RequirementAnalysis:
        """Adjust confidence using final validation and resolver evidence."""

        score = self._confidence_score(analysis)

        if not blocking_missing:
            score += 0.08
        if not blocker_questions:
            score += 0.04
        if analysis.business_rules:
            score += 0.04
        if analysis.candidate_database_objects:
            score += 0.04
        if self._mandatory_fields_present(analysis) and not blocker_questions:
            score = max(score, self.minimum_confidence)

        if blocking_missing or blocker_questions:
            score = min(score, self.minimum_confidence - 0.01)

        if analysis.metadata.get("llm_mode") == "offline_fallback":
            score = min(score, 0.90)

        metadata = dict(analysis.metadata)
        metadata["confidence_score"] = round(max(0.0, min(1.0, score)), 4)
        return analysis.model_copy(update={"metadata": metadata}, deep=True)

    @staticmethod
    def _mandatory_fields_present(analysis: RequirementAnalysis) -> bool:
        """Return whether mandatory SQL-readiness fields are present."""

        missing_fields = analysis.metadata.get("missing_mandatory_fields")
        if isinstance(missing_fields, list):
            return not missing_fields

        known = analysis.known_information
        return all(
            (
                bool(known.season or known.seasons),
                bool(known.sale_range),
                bool(known.area or known.centre or known.garden or known.buyer),
                bool(known.category or known.tea_type),
                bool(known.metrics),
                bool(known.output_grain),
            )
        )

    @staticmethod
    def _copy_with_decision(
        *,
        analysis: RequirementAnalysis,
        decision_status: DecisionStatus,
        reason: str,
        next_action: str,
        sql_generation_allowed: bool,
        status: RequirementStatus,
    ) -> RequirementAnalysis:
        """Return a copy with final decision fields applied."""

        return analysis.model_copy(
            update={
                "decision_status": decision_status,
                "decision_reason": reason,
                "next_action": next_action,
                "sql_generation_allowed": sql_generation_allowed,
                "status": status,
            },
            deep=True,
        )
