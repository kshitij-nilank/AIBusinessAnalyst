from engine.requirement_engine.models import (
    ClarificationQuestion,
    KnownInformation,
    QuestionPriority,
    RequirementAnalysis,
    RequirementStatus,
)
from engine.requirement_engine.validator import RequirementValidator


def _complete_known_information() -> KnownInformation:
    return KnownInformation(
        season=2025,
        sale_range="14 to 26",
        area="AS",
        category="CTC",
        metrics=["quantity", "value", "average price"],
        output_grain="garden-wise",
    )


def _analysis(
    known_information: KnownInformation,
    confidence_score: float = 1.0,
    clarification_questions: list[ClarificationQuestion] | None = None,
) -> RequirementAnalysis:
    return RequirementAnalysis(
        summary="Test requirement",
        known_information=known_information,
        clarification_questions=clarification_questions or [],
        metadata={"confidence_score": confidence_score},
    )


def test_missing_season_blocks_sql() -> None:
    known = _complete_known_information().model_copy(update={"season": None})

    result = RequirementValidator().validate(_analysis(known))

    assert result.sql_generation_allowed is False
    assert result.status == RequirementStatus.NEEDS_CLARIFICATION
    assert "season_or_financial_year" in result.metadata["missing_mandatory_fields"]
    assert any(q.question_id == "Q001_Season" for q in result.clarification_questions)


def test_missing_sale_range_blocks_sql() -> None:
    known = _complete_known_information().model_copy(update={"sale_range": None})

    result = RequirementValidator().validate(_analysis(known))

    assert result.sql_generation_allowed is False
    assert "sale_range_or_date_range" in result.metadata["missing_mandatory_fields"]
    assert any(q.question_id == "Q002_SaleRange" for q in result.clarification_questions)


def test_missing_area_blocks_sql() -> None:
    known = _complete_known_information().model_copy(
        update={"area": None, "centre": None}
    )

    result = RequirementValidator().validate(_analysis(known))

    assert result.sql_generation_allowed is False
    assert "area_centre_or_scope" in result.metadata["missing_mandatory_fields"]
    assert any(q.question_id == "Q003_Area" for q in result.clarification_questions)


def test_missing_metrics_blocks_sql() -> None:
    known = _complete_known_information().model_copy(update={"metrics": []})

    result = RequirementValidator().validate(_analysis(known))

    assert result.sql_generation_allowed is False
    assert "metrics" in result.metadata["missing_mandatory_fields"]
    assert any(q.question_id == "Q005_Metrics" for q in result.clarification_questions)


def test_missing_grouping_blocks_sql() -> None:
    known = _complete_known_information().model_copy(update={"output_grain": None})

    result = RequirementValidator().validate(_analysis(known))

    assert result.sql_generation_allowed is False
    assert "grouping_level" in result.metadata["missing_mandatory_fields"]
    assert any(q.question_id == "Q006_Grouping" for q in result.clarification_questions)


def test_complete_requirement_with_high_confidence_allows_sql() -> None:
    result = RequirementValidator().validate(
        _analysis(_complete_known_information(), confidence_score=0.95)
    )

    assert result.sql_generation_allowed is True
    assert result.status == RequirementStatus.READY_FOR_SQL
    assert result.metadata["confidence_score"] == 0.95
    assert result.metadata["missing_mandatory_fields"] == []


def test_complete_requirement_with_low_confidence_blocks_sql() -> None:
    result = RequirementValidator().validate(
        _analysis(_complete_known_information(), confidence_score=0.75)
    )

    assert result.sql_generation_allowed is False
    assert result.status == RequirementStatus.BLOCKED
    assert result.metadata["confidence_score"] == 0.75


def test_duplicate_clarification_questions_are_not_added() -> None:
    existing_question = ClarificationQuestion(
        question_id="Q001_Season",
        question="Which season or financial year should be used?",
        priority=QuestionPriority.BLOCKER,
        related_field="season",
        expected_answer_format="Season year or financial year.",
    )
    known = _complete_known_information().model_copy(update={"season": None})

    result = RequirementValidator().validate(
        _analysis(known, clarification_questions=[existing_question])
    )

    matching_questions = [
        question
        for question in result.clarification_questions
        if question.question == "Which season or financial year should be used?"
    ]
    assert len(matching_questions) == 1
